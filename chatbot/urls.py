from django.urls import path
from . import views

urlpatterns = [
    path('chat/', views.ChatBotView.as_view(), name='chatbot'),    
    path('classify/', views.ClassifyMessageView.as_view(), name='classify'),
    path('history/', views.ChatHistoryView.as_view(), name='chat_history'),
    path('summarize-note/', views.SummarizeNoteView.as_view(), name='summarize_note'),
    path('summarize-document/', views.DocumentSummarizerView.as_view(), name='summarize_document'),
]
