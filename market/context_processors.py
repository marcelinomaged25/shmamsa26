def notifications(request):
    """Expose the current team's notifications to every template so the
    navbar bell/dropdown can show them without every view needing to pass
    them in explicitly."""
    if not request.user.is_authenticated:
        return {}

    profile = getattr(request.user, 'profile', None)
    if profile is None:
        return {}

    nav_notifications = profile.notifications.all()[:8]
    unread_count = profile.notifications.filter(is_read=False).count()

    return {
        'nav_notifications': nav_notifications,
        'unread_notification_count': unread_count,
    }
