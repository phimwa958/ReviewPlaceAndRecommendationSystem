import re
from django.db.models.signals import post_save
from django.dispatch import receiver
from django.contrib.contenttypes.models import ContentType
from .models import Review, Comment, Notification, Place, PlaceLike, Report, CustomUser, UserActivity

@receiver(post_save, sender=Review)
def create_review_notification(sender, instance, created, **kwargs):
    if created:
        if instance.place.owner:
            if instance.user != instance.place.owner:
                Notification.objects.create(
                    recipient=instance.place.owner,
                    actor=instance.user,
                    verb='ได้รีวิวสถานที่ของคุณ',
                    target=instance.place,
                    action_object=instance
                )
    else:
        # This handles notifications for review edits.
        if instance.place.owner:
            if instance.user != instance.place.owner:
                Notification.objects.create(
                    recipient=instance.place.owner,
                    actor=instance.user,
                    verb='ได้แก้ไขรีวิวในสถานที่ของคุณ',
                    target=instance.place,
                    action_object=instance
                )

@receiver(post_save, sender=Comment)
def create_comment_notification(sender, instance, created, **kwargs):
    if created:
        # Notify review owner
        if instance.review.user != instance.user:
            Notification.objects.create(
                recipient=instance.review.user,
                actor=instance.user,
                verb='ได้แสดงความคิดเห็นในรีวิวของคุณ',
                target=instance.review,
                action_object=instance
            )

        # Notify mentioned users
        mentioned_usernames = set(re.findall(r'@(\w+)', instance.text))
        for username in mentioned_usernames:
            try:
                mentioned_user = CustomUser.objects.get(username=username)
                if mentioned_user != instance.user and mentioned_user != instance.review.user:
                    Notification.objects.create(
                        recipient=mentioned_user,
                        actor=instance.user,
                        verb='ได้กล่าวถึงคุณในความคิดเห็น',
                        target=instance.review,
                        action_object=instance
                    )
            except CustomUser.DoesNotExist:
                pass
    else:
        # Notify review owner that a comment on their review was edited
        if instance.review.user != instance.user:
            Notification.objects.create(
                recipient=instance.review.user,
                actor=instance.user,
                verb='ได้แก้ไขความคิดเห็นในรีวิวของคุณ',
                target=instance.review,
                action_object=instance
            )
        # Notify mentioned users
        mentioned_usernames = set(re.findall(r'@(\w+)', instance.text))
        for username in mentioned_usernames:
            try:
                mentioned_user = CustomUser.objects.get(username=username)
                if mentioned_user != instance.user and mentioned_user != instance.review.user:
                    Notification.objects.create(
                        recipient=mentioned_user,
                        actor=instance.user,
                        verb='ได้กล่าวถึงคุณในความคิดเห็น',
                        target=instance.review,
                        action_object=instance
                    )
            except CustomUser.DoesNotExist:
                pass

@receiver(post_save, sender=PlaceLike)
def create_like_notification(sender, instance, created, **kwargs):
    if created:
        if instance.place.owner:
            if instance.user != instance.place.owner:
                Notification.objects.create(
                    recipient=instance.place.owner,
                    actor=instance.user,
                    verb='ถูกใจสถานที่ของคุณ',
                    target=instance.place,
                    action_object=instance
                )

@receiver(post_save, sender=UserActivity)
def create_share_notification(sender, instance, created, **kwargs):
    if created and instance.activity_type == 'share':
        if instance.content_object and isinstance(instance.content_object, Place) and instance.content_object.owner:
            if instance.user != instance.content_object.owner:
                Notification.objects.create(
                    recipient=instance.content_object.owner,
                    actor=instance.user,
                    verb='ได้แชร์สถานที่ของคุณ',
                    target=instance.content_object,
                    action_object=instance
                )

@receiver(post_save, sender=Report)
def create_report_notification(sender, instance, created, **kwargs):
    if created:
        admins = CustomUser.objects.filter(is_superuser=True)
        
        content_object = None
        if instance.report_type == 'place':
            content_object = instance.place
        elif instance.report_type == 'review':
            content_object = instance.review
        elif instance.report_type == 'comment':
            content_object = instance.comment

        for admin in admins:
            Notification.objects.create(
                recipient=admin,
                actor=instance.reported_by,
                verb=f'ได้รายงาน{instance.get_report_type_display()}',
                target=content_object,
                action_object=instance
            )
