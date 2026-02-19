from django.contrib import admin
from django.urls import path, include
from django.contrib.auth import views as auth_views
from django.conf import settings
from django.conf.urls.static import static

urlpatterns = [
    path('admin/', admin.site.urls),
    path('', include('apps.dashboard.urls')),
    path('login/', auth_views.LoginView.as_view(template_name='base/login.html'), name='login'),
    path('logout/', auth_views.LogoutView.as_view(), name='logout'),
    path('dashboard/', include('apps.dashboard.urls')),
    path('parts/', include('apps.parts.urls')),
    path('companies/', include('apps.companies.urls')),
    path('inventory/', include('apps.inventory.urls')),
    path('rfq/', include('apps.rfq.urls')),
    path('quotes/', include('apps.quotes.urls')),
    path('sales-orders/', include('apps.sales_orders.urls')),
    path('purchase-orders/', include('apps.purchase_orders.urls')),
    path('receiving/', include('apps.receiving.urls')),
    path('email/', include('apps.email_integration.urls')),
    path('vendor-rfq/', include('apps.vendor_rfq.urls')),
] + static(settings.MEDIA_URL, document_root=settings.MEDIA_ROOT)
