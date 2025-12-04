from django.contrib import admin
from django.urls import path, include

urlpatterns = [
    path('admin/', admin.site.urls),
    path('auth/', include('authentication.urls'), name='authentication'),
    path('subscription/', include('subscription.urls'), name='subscription'),
    path('actions/', include('actions.urls'), name='actions'),
    path('chatbot/', include('chatbot.urls'), name='chatbot'),
    path('admin-panel/', include('admin_panel.urls'), name='admin_panel'),
]
