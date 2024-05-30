from django.urls import path, include
from django.contrib import admin

urlpatterns = [
    path('admin/', admin.site.urls),
    path('manage/', include('staffpage.urls')),
    path('files/', include('rawstatus.urls')),
    path('datasets/', include('datasets.urls')),
    path('jobs/', include('jobs.urls')),
    path('dash/', include('dashboard.urls')),
    path('', include('django.contrib.auth.urls')),
    path('', include('home.urls')),
    path('analysis/', include('analysis.urls')),
]
