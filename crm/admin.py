from django.contrib import admin
from django.contrib.auth import get_user_model
from django.contrib.auth.admin import UserAdmin as BaseUserAdmin

from .models import (ActivityLog, AdSpend, Attendance, Center, Charge, Expense, Grade, Group,
                     Lead, LeadCall, Lesson, Payment, Promo, Script, Staff, StatusChange, Student, Task)

admin.site.site_header = "Markaz CRM boshqaruvi"
admin.site.site_title = "Markaz CRM"
admin.site.index_title = "Ma'lumotlar"

User = get_user_model()


class StaffInline(admin.StackedInline):
    model = Staff
    can_delete = False
    verbose_name_plural = "Rol"


admin.site.unregister(User)


@admin.register(User)
class UserAdmin(BaseUserAdmin):
    inlines = [StaffInline]


@admin.register(Center)
class CenterAdmin(admin.ModelAdmin):
    list_display = ("name", "director", "phone", "plan_income", "plan_expense")


@admin.register(Staff)
class StaffAdmin(admin.ModelAdmin):
    list_display = ("user", "role")
    list_filter = ("role",)


@admin.register(Group)
class GroupAdmin(admin.ModelAdmin):
    list_display = ("name", "course", "teacher", "days", "time", "room", "price", "capacity", "branch")
    list_filter = ("branch", "pay_model")
    search_fields = ("name", "course", "teacher")


class LeadCallInline(admin.TabularInline):
    model = LeadCall
    extra = 0


@admin.register(Lead)
class LeadAdmin(admin.ModelAdmin):
    list_display = ("name", "phone", "course", "source", "status", "next_contact", "trial_date", "created_at")
    list_filter = ("status", "source", "trial_result")
    search_fields = ("name", "phone", "course")
    inlines = [LeadCallInline]


@admin.register(LeadCall)
class LeadCallAdmin(admin.ModelAdmin):
    list_display = ("lead", "date", "text")
    search_fields = ("lead__name", "text")


class StatusChangeInline(admin.TabularInline):
    model = StatusChange
    extra = 0
    fields = ("date", "status")


@admin.register(Student)
class StudentAdmin(admin.ModelAdmin):
    inlines = [StatusChangeInline]
    list_display = ("name", "phone", "group", "status", "join_date", "discount")
    list_filter = ("status", "group")
    search_fields = ("name", "phone", "parent")
    autocomplete_fields = ("group", "referrer", "lead")


@admin.register(Payment)
class PaymentAdmin(admin.ModelAdmin):
    list_display = ("student", "amount", "month", "method", "date", "refund")
    list_filter = ("month", "method", "refund")
    search_fields = ("student__name",)
    autocomplete_fields = ("student",)


@admin.register(Charge)
class ChargeAdmin(admin.ModelAdmin):
    list_display = ("student", "month", "amount")
    list_filter = ("month",)


class AttendanceInline(admin.TabularInline):
    model = Attendance
    extra = 0
    autocomplete_fields = ("student",)


@admin.register(Lesson)
class LessonAdmin(admin.ModelAdmin):
    list_display = ("group", "date", "topic")
    list_filter = ("group",)
    date_hierarchy = "date"
    inlines = [AttendanceInline]


@admin.register(Attendance)
class AttendanceAdmin(admin.ModelAdmin):
    list_display = ("student", "lesson", "status")
    list_filter = ("status",)


@admin.register(Grade)
class GradeAdmin(admin.ModelAdmin):
    list_display = ("student", "title", "score", "max_score", "date")
    search_fields = ("student__name", "title")


@admin.register(Expense)
class ExpenseAdmin(admin.ModelAdmin):
    list_display = ("title", "category", "amount", "month", "date", "teacher")
    list_filter = ("category", "month")


@admin.register(AdSpend)
class AdSpendAdmin(admin.ModelAdmin):
    list_display = ("source", "amount", "month", "note")
    list_filter = ("source", "month")


@admin.register(Promo)
class PromoAdmin(admin.ModelAdmin):
    list_display = ("code", "type", "value", "active")
    list_filter = ("active", "type")


@admin.register(Script)
class ScriptAdmin(admin.ModelAdmin):
    list_display = ("title",)


@admin.register(Task)
class TaskAdmin(admin.ModelAdmin):
    list_display = ("title", "assignee", "due", "done")
    list_filter = ("done",)


@admin.register(ActivityLog)
class ActivityLogAdmin(admin.ModelAdmin):
    list_display = ("at", "user", "text")
    readonly_fields = ("at", "user", "text")
    search_fields = ("text",)
