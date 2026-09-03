import os
import time
from collections import defaultdict
from datetime import datetime, timedelta
from typing import List

from fastapi import FastAPI, Depends, HTTPException, status, Request, Response, BackgroundTasks
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import Response, JSONResponse
from fastapi.security import OAuth2PasswordBearer, OAuth2PasswordRequestForm
from jose import JWTError, jwt
from passlib.context import CryptContext
from sqlalchemy.orm import Session
from sqlalchemy import func

from app.database import Base, engine, get_db
from app import models, schemas, services

# Database Initialization
Base.metadata.create_all(bind=engine)

# Security Constants
SECRET_KEY = os.getenv("SECRET_KEY", "super-secret-jwt-key-change-this")
ALGORITHM = os.getenv("ALGORITHM", "HS256")
ACCESS_TOKEN_EXPIRE_MINUTES = 60

pwd_context = CryptContext(schemes=["bcrypt"], deprecated="auto")
oauth2_scheme = OAuth2PasswordBearer(tokenUrl="/auth/login")

app = FastAPI(title="Embeddable Widget & Lead-Capture Platform")

# CORS Setup - Enables cross-origin loading and form submission
app.add_middleware(
    CORSMiddleware,
    allow_origins=["*"],
    allow_credentials=True,
    allow_methods=["*"],
    allow_headers=["*"],
)

# Custom In-Memory Rate Limiter (10 requests per minute per IP)
rate_limit_records = defaultdict(list)
RATE_LIMIT_MAX_REQUESTS = 10
RATE_LIMIT_WINDOW_SECONDS = 60

@app.middleware("http")
async def rate_limit_middleware(request: Request, call_next):
    if request.url.path == "/submissions" and request.method == "POST":
        client_ip = request.client.host
        now = time.time()
        
        # Clean expired timestamps
        rate_limit_records[client_ip] = [
            t for t in rate_limit_records[client_ip] if now - t < RATE_LIMIT_WINDOW_SECONDS
        ]
        
        if len(rate_limit_records[client_ip]) >= RATE_LIMIT_MAX_REQUESTS:
            return JSONResponse(
                status_code=status.HTTP_429_TOO_MANY_REQUESTS,
                content={"detail": "Rate limit exceeded. Please wait before submitting again."}
            )
        
        rate_limit_records[client_ip].append(now)

    return await call_next(request)

# Auth Helpers
def verify_password(plain_password, hashed_password):
    return pwd_context.verify(plain_password, hashed_password)

def get_password_hash(password):
    return pwd_context.hash(password)

def create_access_token(data: dict):
    to_encode = data.copy()
    expire = datetime.utcnow() + timedelta(minutes=ACCESS_TOKEN_EXPIRE_MINUTES)
    to_encode.update({"exp": expire})
    return jwt.encode(to_encode, SECRET_KEY, algorithm=ALGORITHM)

def get_current_user(token: str = Depends(oauth2_scheme), db: Session = Depends(get_db)) -> models.User:
    credentials_exception = HTTPException(
        status_code=status.HTTP_401_UNAUTHORIZED,
        detail="Could not validate credentials",
        headers={"WWW-Authenticate": "Bearer"},
    )
    try:
        payload = jwt.decode(token, SECRET_KEY, algorithms=[ALGORITHM])
        user_id: str = payload.get("sub")
        if user_id is None:
            raise credentials_exception
    except JWTError:
        raise credentials_exception
    
    user = db.query(models.User).filter(models.User.id == user_id).first()
    if user is None:
        raise credentials_exception
    return user

# System Health Check
@app.get("/health")
def health_check():
    return {"status": "healthy", "timestamp": datetime.utcnow().isoformat()}

# Authentication Endpoints
@app.post("/auth/register", response_model=schemas.UserResponse, status_code=status.HTTP_201_CREATED)
def register(user_in: schemas.UserCreate, db: Session = Depends(get_db)):
    db_user = db.query(models.User).filter(models.User.email == user_in.email).first()
    if db_user:
        raise HTTPException(status_code=400, detail="Email already registered")
    
    user = models.User(
        email=user_in.email,
        hashed_password=get_password_hash(user_in.password)
    )
    db.add(user)
    db.commit()
    db.refresh(user)
    return user

@app.post("/auth/login", response_model=schemas.Token)
def login(form_data: OAuth2PasswordRequestForm = Depends(), db: Session = Depends(get_db)):
    user = db.query(models.User).filter(models.User.email == form_data.username).first()
    if not user or not verify_password(form_data.password, user.hashed_password):
        raise HTTPException(status_code=400, detail="Incorrect email or password")
    
    access_token = create_access_token(data={"sub": user.id})
    return {"access_token": access_token, "token_type": "bearer"}

# Widget Admin Management API (Tenant Isolated)
@app.post("/api/widgets", response_model=schemas.WidgetResponse, status_code=status.HTTP_201_CREATED)
def create_widget(
    widget_in: schemas.WidgetCreate,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    widget = models.Widget(
        owner_id=current_user.id,
        title=widget_in.title,
        widget_type=widget_in.widget_type,
        button_text=widget_in.button_text
    )
    db.add(widget)
    db.commit()
    db.refresh(widget)
    
    base_url = str(request.base_url).rstrip("/")
    widget.embed_snippet = f'<script src="{base_url}/widget.js?id={widget.id}"></script>'
    return widget

@app.get("/api/widgets", response_model=List[schemas.WidgetResponse])
def list_widgets(
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    widgets = db.query(models.Widget).filter(models.Widget.owner_id == current_user.id).all()
    base_url = str(request.base_url).rstrip("/")
    for w in widgets:
        w.embed_snippet = f'<script src="{base_url}/widget.js?id={w.id}"></script>'
    return widgets

@app.get("/api/widgets/{widget_id}", response_model=schemas.WidgetResponse)
def get_widget(
    widget_id: str,
    request: Request,
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    # Tenant-isolation enforcement
    widget = db.query(models.Widget).filter(
        models.Widget.id == widget_id,
        models.Widget.owner_id == current_user.id
    ).first()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget not found")
    
    base_url = str(request.base_url).rstrip("/")
    widget.embed_snippet = f'<script src="{base_url}/widget.js?id={widget.id}"></script>'
    return widget

# Public Delivery Endpoints (Cached & Versioned Assets)
@app.get("/widgets/{widget_id}/config")
def get_widget_config(widget_id: str, db: Session = Depends(get_db)):
    widget = db.query(models.Widget).filter(models.Widget.id == widget_id).first()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget configuration not found")
    
    headers = {"Cache-Control": "public, max-age=60"}
    return JSONResponse(
        content={
            "id": widget.id,
            "title": widget.title,
            "widget_type": widget.widget_type,
            "button_text": widget.button_text
        },
        headers=headers
    )

@app.get("/widget.js")
def get_widget_script(request: Request):
    base_url = str(request.base_url).rstrip("/")
    
    # Pure JavaScript bundle that executes cross-origin on customer site
    js_code = f"""
(function() {{
    const scriptTag = document.currentScript;
    const urlParams = new URLSearchParams(scriptTag.src.split('?')[1]);
    const widgetId = urlParams.get('id');

    if (!widgetId) {{
        console.error('Widget script missing "id" parameter');
        return;
    }}

    const apiBase = "{base_url}";

    fetch(`${{apiBase}}/widgets/${{widgetId}}/config`)
        .then(res => res.json())
        .then(config => {{
            const container = document.createElement('div');
            container.style.border = "1px solid #ccc";
            container.style.padding = "16px";
            container.style.borderRadius = "8px";
            container.style.maxWidth = "350px";
            container.style.fontFamily = "sans-serif";
            container.style.boxShadow = "0 2px 5px rgba(0,0,0,0.1)";

            container.innerHTML = `
                <h3 style="margin-top:0;">${{config.title}}</h3>
                <form id="widget-form-${{widgetId}}">
                    <input type="text" name="hp_field" style="display:none !important;" tabindex="-1" autocomplete="off">
                    <div style="margin-bottom:8px;">
                        <input type="text" name="name" placeholder="Your Name" style="width:100%; padding:8px; box-sizing:border-box;">
                    </div>
                    <div style="margin-bottom:8px;">
                        <input type="email" name="email" placeholder="Your Email" required style="width:100%; padding:8px; box-sizing:border-box;">
                    </div>
                    <button type="submit" style="width:100%; padding:8px; background:#0066cc; color:#fff; border:none; border-radius:4px; cursor:pointer;">
                        ${{config.button_text}}
                    </button>
                </form>
                <div id="widget-msg-${{widgetId}}" style="margin-top:8px;"></div>
            `;

            scriptTag.parentNode.insertBefore(container, scriptTag.nextSibling);

            document.getElementById(`widget-form-${{widgetId}}`).addEventListener('submit', function(e) {{
                e.preventDefault();
                const formData = new FormData(this);
                const payload = {{
                    widget_id: widgetId,
                    name: formData.get('name'),
                    email: formData.get('email'),
                    hp_field: formData.get('hp_field')
                }};

                fetch(`${{apiBase}}/submissions`, {{
                    method: 'POST',
                    headers: {{ 'Content-Type': 'application/json' }},
                    body: JSON.stringify(payload)
                }})
                .then(async res => {{
                    const data = await res.json();
                    if (!res.ok) throw new Error(data.detail || 'Submission failed');
                    return data;
                }})
                .then(data => {{
                    document.getElementById(`widget-msg-${{widgetId}}`).innerText = "Thank you! Response recorded.";
                    this.reset();
                }})
                .catch(err => {{
                    document.getElementById(`widget-msg-${{widgetId}}`).innerText = "Error: " + err.message;
                }});
            }});
        }})
        .catch(err => console.error('Failed to load widget config:', err));
}})();
"""
    return Response(
        content=js_code,
        media_type="application/javascript",
        headers={"Cache-Control": "public, max-age=31536000, immutable"}
    )

# Public Submission API
@app.post("/submissions", response_model=schemas.SubmissionResponse, status_code=status.HTTP_201_CREATED)
async def create_submission(
    sub_in: schemas.SubmissionCreate,
    request: Request,
    background_tasks: BackgroundTasks,
    db: Session = Depends(get_db)
):
    # 1. Spam Filtering (Honeypot Trap)
    if sub_in.hp_field:
        # Silently reject automated bot submissions
        return Response(status_code=status.HTTP_200_OK, content='{"status":"ignored"}', media_type="application/json")

    # 2. Check widget existence
    widget = db.query(models.Widget).filter(models.Widget.id == sub_in.widget_id).first()
    if not widget:
        raise HTTPException(status_code=404, detail="Widget target not found")

    # 3. Geo Enrichment Fallback Chain
    client_ip = request.client.host
    geo_data = await services.fetch_geo_data(client_ip)

    # 4. Save Main Submission Payload
    submission = models.Submission(
        widget_id=sub_in.widget_id,
        payload={"name": sub_in.name, "email": sub_in.email, **sub_in.extra_data},
        ip_address=client_ip,
        geo_country=geo_data.get("country"),
        geo_city=geo_data.get("city")
    )
    db.add(submission)
    db.commit()
    db.refresh(submission)

    # 5. Non-Blocking Side Effect
    background_tasks.add_task(
        services.send_confirmation_email_side_effect,
        email=sub_in.email,
        submission_id=submission.id
    )

    return submission

# Owner Analytics Dashboard
@app.get("/api/dashboard/stats")
def get_dashboard_stats(
    current_user: models.User = Depends(get_current_user),
    db: Session = Depends(get_db)
):
    user_widget_ids = [
        w.id for w in db.query(models.Widget.id).filter(models.Widget.owner_id == current_user.id).all()
    ]
    
    total_widgets = len(user_widget_ids)
    total_submissions = db.query(models.Submission).filter(
        models.Submission.widget_id.in_(user_widget_ids)
    ).count() if user_widget_ids else 0

    geo_breakdown = db.query(
        models.Submission.geo_country, func.count(models.Submission.id)
    ).filter(
        models.Submission.widget_id.in_(user_widget_ids)
    ).group_by(models.Submission.geo_country).all() if user_widget_ids else []

    return {
        "total_widgets": total_widgets,
        "total_submissions": total_submissions,
        "geo_breakdown": {country or "Unknown": count for country, count in geo_breakdown}
    }