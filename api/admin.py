from django.contrib import admin
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin
from .models import User, Zone, PC, Tariff, Booking, Payment, Tournament, News

@admin.register(User)
class UserAdmin(BaseUserAdmin):
    list_display  = ('username', 'email', 'role', 'balance', 'is_active')
    list_filter   = ('role', 'is_active')
    fieldsets     = BaseUserAdmin.fieldsets + (
        ('NEXUS', {'fields': ('phone', 'balance', 'role', 'avatar')}),
    )

admin.site.register(Zone)
admin.site.register(PC)
admin.site.register(Tariff)
admin.site.register(Booking)
admin.site.register(Payment)
admin.site.register(Tournament)
admin.site.register(News)