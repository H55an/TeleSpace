from fastapi import Depends, HTTPException, status
from fastapi.security import HTTPBearer, HTTPAuthorizationCredentials
from app.shared.database import auth as db_auth

# هذا الكائن السحري هو الذي يظهر القفل في Swagger ويدير المصادقة
security = HTTPBearer()

def get_current_user(credentials: HTTPAuthorizationCredentials = Depends(security)) -> int:
    """
    يستلم التوكن جاهزاً من Swagger أو التطبيق ويتحقق منه.
    """
    # 1. استخراج التوكن (FastAPI قامت بالفعل بفصل كلمة Bearer عنك)
    token = credentials.credentials
    
    # 2. التحقق في قاعدة البيانات
    user_id = db_auth.verify_access_token(token)

    if not user_id:
        raise HTTPException(
            status_code=status.HTTP_401_UNAUTHORIZED,
            detail="Invalid or expired token",
        )

    return user_id