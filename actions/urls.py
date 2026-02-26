from django.urls import path
from . import views



urlpatterns = [
    path('events/', views.EventListView.as_view(), name='events'),
    path('events/<uuid:pk>/', views.EventDetailView.as_view(), name='event_detail'),
    
    path('tasks/', views.TaskListView.as_view(), name='tasks'),
    path('tasks/<uuid:pk>/', views.TaskDetailView.as_view(), name='task_detail'),
    
    path('notes/', views.NoteListView.as_view(), name='notes'),
    path('notes/<uuid:pk>/', views.NoteDetailView.as_view(), name='note_detail'),
    
    path('test-call/', views.MakeCallView.as_view(), name='test_call'),
    path('test-fcm/', views.TestFCMView.as_view(), name='test_fcm'),
    
    # Public API endpoints for FCM
    path('health/', views.HealthCheckView.as_view(), name='health'),
    path('send-notification/', views.SendNotificationView.as_view(), name='send_notification'),
]