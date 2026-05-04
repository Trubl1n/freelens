from django.contrib.auth import views as auth_views
from django.urls import path

from . import views

app_name = "core"

urlpatterns = [
    path("", views.index, name="index"),
    path("register/", views.RegisterView.as_view(), name="register"),
    path("accounts/login/", views.CustomLoginView.as_view(), name="login"),
    path("accounts/logout/", auth_views.LogoutView.as_view(next_page="core:login"), name="logout"),
    path("dashboard/", views.DashboardView.as_view(), name="dashboard"),
    path("profile/", views.ProfileUpdateView.as_view(), name="profile"),
    path("profile/analyze/", views.analyze_freelance, name="profile-analyze"),
    path("platforms/", views.PlatformListView.as_view(), name="platform-list"),
    path("platforms/create/", views.PlatformCreateView.as_view(), name="platform-create"),
    path(
        "platforms/<int:pk>/update/",
        views.PlatformUpdateView.as_view(),
        name="platform-update",
    ),
    path(
        "platforms/<int:pk>/delete/",
        views.PlatformDeleteView.as_view(),
        name="platform-delete",
    ),
    path("orders/", views.OrderListView.as_view(), name="order-list"),
    path("orders/create/", views.OrderCreateView.as_view(), name="order-create"),
    path("orders/<int:pk>/", views.OrderDetailView.as_view(), name="order-detail"),
    path(
        "orders/<int:pk>/update/",
        views.OrderUpdateView.as_view(),
        name="order-update",
    ),
    path(
        "orders/<int:pk>/ai-evaluate/",
        views.order_save_and_ai_evaluate,
        name="order-ai-evaluate",
    ),
    path(
        "orders/<int:pk>/ai-evaluate-only/",
        views.order_ai_evaluate,
        name="order-ai-evaluate-only",
    ),
]
