from django.urls import path, include
from rest_framework.routers import DefaultRouter
from rest_framework_simplejwt.views import TokenRefreshView
from . import views

router = DefaultRouter()
router.register('pcs',         views.PCViewSet,         basename='pc')
router.register('tariffs',     views.TariffViewSet,     basename='tariff')
router.register('bookings',    views.BookingViewSet,     basename='booking')
router.register('tournaments', views.TournamentViewSet,  basename='tournament')
router.register('news',        views.NewsViewSet,        basename='news')
router.register('users',       views.UserViewSet,        basename='user')

urlpatterns = [
    # Авторизация
    path('auth/register/',          views.RegisterView.as_view()),
    path('auth/login/',             views.LoginView.as_view()),
    path('auth/logout/',            views.LogoutView.as_view()),
    path('auth/token/refresh/',     TokenRefreshView.as_view()),

    # Профиль и баланс
    path('profile/',                views.ProfileView.as_view()),
    path('payments/topup/',         views.TopUpView.as_view()),
    path('payments/history/',       views.PaymentHistoryView.as_view()),

    # Все остальные эндпоинты через роутер
    path('', include(router.urls)),
]