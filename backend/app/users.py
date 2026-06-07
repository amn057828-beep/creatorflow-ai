from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.database import get_db
from app.dependencies import get_current_user
from app.models import User, Project, Script, Audio

router = APIRouter(prefix="/me", tags=["Me"])


@router.get("")
def get_me(
    db: Session = Depends(get_db),
    current_user: User = Depends(get_current_user)
):
    projects_count = db.query(Project).filter(Project.user_id == current_user.id).count()
    scripts_count = db.query(Script).filter(Script.user_id == current_user.id).count()
    audios_count = db.query(Audio).filter(Audio.user_id == current_user.id).count()

    return {
        "user": {
            "id": current_user.id,
            "name": current_user.name,
            "email": current_user.email,
            "role": current_user.role,
            "credits": current_user.credits,
            "is_active": current_user.is_active,
            "created_at": current_user.created_at
        },
        "stats": {
            "projects": projects_count,
            "scripts": scripts_count,
            "audios": audios_count
        }
    }
