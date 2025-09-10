from celery import Celery
from app.core.config import get_settings

settings = get_settings()

# Initialize Celery app
celery_app = Celery(
    "oxygen_pred",
    broker=settings.CELERY_BROKER_URL,
    backend=settings.CELERY_RESULT_BACKEND,
)

celery_app.conf.update(
    task_serializer="json",
    accept_content=["json"],
    result_serializer="json",
    timezone="UTC",
    enable_utc=True,
)


@celery_app.task
def process_telemetry_batch(telemetry_ids: list):
    """
    Background task to process a batch of telemetry records
    Triggers enrichment pipeline (Stages 1-4)
    """
    pass


@celery_app.task
def generate_depletion_prediction(session_id: str):
    """
    Background task to generate depletion prediction for a session
    """
    pass


@celery_app.task
def generate_surge_forecast(region_code: str):
    """
    Background task to generate climate surge forecast for a region
    """
    pass
