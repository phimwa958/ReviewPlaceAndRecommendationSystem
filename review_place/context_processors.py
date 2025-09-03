from .models import Notification

def unread_notifications(request):
    if request.user.is_authenticated:
        return {'unread_notifications': request.user.notifications.filter(unread=True).count()}
    return {'unread_notifications': 0}
