import logging
from celery import shared_task
from django.contrib.auth import get_user_model

logger = logging.getLogger(__name__)
User = get_user_model()

@shared_task
def award_referral_points_task(user_id):
    """
    Celery task to award referral points asynchronously.
    """
    from .services import award_referral_points
    try:
        user = User.objects.get(id=user_id)
        award_referral_points(user)
    except User.DoesNotExist:
        logger.warning(f"Failed to award referral points: User {user_id} does not exist.")
    except Exception as e:
        logger.error(f"Error awarding referral points for user {user_id}: {e}")
