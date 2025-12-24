from django.contrib import admin

from amelie.personal_tab.models import DiscountPeriod, Discount, DiscountCredit, Transaction, \
    CustomTransaction, ActivityTransaction, CookieCornerTransaction, AlexiaTransaction, ContributionTransaction, \
    Article, Category, RFIDCard, AuthorizationType, Authorization, Amendment, DebtCollectionAssignment, \
    DebtCollectionBatch, \
    DebtCollectionInstruction, Reversal, DebtCollectionTransaction, ReversalTransaction, LedgerAccount, PrintLogEntry


class RFIDAdmin(admin.ModelAdmin):
    list_display = ('id', '__str__', 'person', 'active', 'created', 'last_used')
    list_filter = ('active',)
    raw_id_fields = ('person',)
    search_fields = ['code', 'person__slug']


class CookieCornerTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'article', 'amount', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on')
    date_hierarchy = 'date'
    search_fields = ['article__name_nl', 'article__name_en', 'person__slug']
    raw_id_fields = ('person', 'discount', 'debt_collection',)
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(CookieCornerTransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(CookieCornerTransactionAdmin, self).has_delete_permission(request, obj)


class TransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug']
    raw_id_fields = ('person', 'discount', 'debt_collection',)
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_add_permission(self, request):
        return False

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(TransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(TransactionAdmin, self).has_delete_permission(request, obj)


class CustomTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug']
    raw_id_fields = ('person', 'discount', 'debt_collection',)
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(CustomTransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(CustomTransactionAdmin, self).has_delete_permission(request, obj)


class ActivityTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'event', 'description', 'price', 'person', 'discount', 'date', 'with_enrollment_options', 'added_on')
    list_filter = ('date', 'added_on', 'with_enrollment_options')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug', 'event__summary_nl', 'event__summary_en']
    raw_id_fields = ('person', 'discount', 'debt_collection', 'event', 'participation')
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(ActivityTransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(ActivityTransactionAdmin, self).has_delete_permission(request, obj)


class AlexiaTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'transaction_id', 'description', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug', 'transaction_id']
    raw_id_fields = ('person', 'discount', 'debt_collection')
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(AlexiaTransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(AlexiaTransactionAdmin, self).has_delete_permission(request, obj)


class ContributionTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'membership', 'description', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug']
    raw_id_fields = ('person', 'membership', 'discount', 'debt_collection')
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(ContributionTransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(ContributionTransactionAdmin, self).has_delete_permission(request, obj)


class DebtCollectionTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'description', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug']
    raw_id_fields = ('person', 'discount', 'debt_collection')
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(DebtCollectionTransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(DebtCollectionTransactionAdmin, self).has_delete_permission(request, obj)


class ReversalTransactionAdmin(admin.ModelAdmin):
    list_display = ('id', 'reversal', 'description', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug']
    raw_id_fields = ('person', 'reversal', 'discount', 'debt_collection')
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']

    # Jelte 2015-04-01: Disable mass deletion because has_delete_permission seems to be ignored
    actions = None

    def has_change_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(ReversalTransactionAdmin, self).has_change_permission(request, obj)

    def has_delete_permission(self, request, obj=None):
        if obj and obj.debt_collection:
            return False
        else:
            return super(ReversalTransactionAdmin, self).has_delete_permission(request, obj)


class CategoryAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_nl', 'name_en', 'is_available', 'order')
    list_editable = ('order',)
    list_filter = ('is_available',)
    search_fields = ['name_nl', 'name_en']


class DiscountPeriodInline(admin.TabularInline):
    model = DiscountPeriod.articles.through


class ArticleAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_nl', 'name_en', 'category', 'ledger_account', 'price', 'is_available', 'kcal')
    list_filter = ('category', 'ledger_account', 'is_available')
    list_editable = ('ledger_account', 'price', 'is_available', 'kcal')
    search_fields = ['name_nl', 'name_en']
    inlines = [DiscountPeriodInline, ]


class AuthorizationTypeAdmin(admin.ModelAdmin):
    list_display = ('id', 'name_nl', 'name_en', 'active', 'contribution', 'consumptions', 'activities', 'other_payments')
    list_filter = ('active', 'contribution', 'consumptions', 'activities', 'other_payments')
    search_fields = ['name_nl', 'name_en', 'text_nl', 'text_en']


class AmendmentInline(admin.TabularInline):
    model = Amendment
    extra = 1
    max_num = 1


class AuthorizationAdmin(admin.ModelAdmin):
    list_display = ('id', 'authorization_type', 'person', 'iban', 'bic', 'is_signed', 'start_date', 'end_date',)
    list_filter = ('authorization_type', 'is_signed',)
    search_fields = ['person__first_name', 'person__last_name', 'iban', 'account_holder_name']
    date_hierarchy = 'start_date'
    raw_id_fields = ('person',)
    inlines = [AmendmentInline, ]


class AmendmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'authorization', 'date', 'previous_iban', 'previous_bic', 'other_bank',)
    list_filter = ('other_bank',)
    date_hierarchy = 'date'
    raw_id_fields = ('authorization',)


class DebtCollectionAssignmentAdmin(admin.ModelAdmin):
    list_display = ('id', 'created_on', 'description', 'start', 'end',)
    search_fields = ['description', ]
    date_hierarchy = 'created_on'

    def has_add_permission(self, request):
        return False


class DebtCollectionBatchAdmin(admin.ModelAdmin):
    list_display = ('id', 'assignment', 'execution_date', 'sequence_type', 'status',)
    list_filter = ('sequence_type', 'status',)
    search_fields = ['assignment__description', ]
    date_hierarchy = 'execution_date'
    raw_id_fields = ('assignment',)

    def has_add_permission(self, request):
        return False


class DebtCollectionInstructionAdmin(admin.ModelAdmin):
    list_display = ('id', 'batch', 'authorization', 'end_to_end_id', 'amount',)
    search_fields = ['authorization__person__first_name', 'authorization__person__last_name',
                     'authorization__iban', 'authorization__account_holder_name', 'description']
    raw_id_fields = ('batch', 'authorization',)

    def has_add_permission(self, request):
        return False


class ReversalAdmin(admin.ModelAdmin):
    list_display = ('id', 'instruction', 'date', 'pre_settlement', 'reason',)
    list_filter = ('pre_settlement',)
    raw_id_fields = ('instruction',)
    date_hierarchy = 'date'

    def has_add_permission(self, request):
        return False


class DiscountPeriodAdmin(admin.ModelAdmin):
    list_display = ('id', 'description_nl', 'description_en', 'begin', 'end', 'ledger_account_number',
                    'balance_account_number')
    list_filter = ('begin', 'end')
    date_hierarchy = 'begin'
    filter_horizontal = ('articles',)
    search_fields = ['description_nl', 'description_en']


class DiscountAdmin(admin.ModelAdmin):
    list_display = ('id', 'discount_period', 'amount', 'date')
    list_filter = ('date',)
    date_hierarchy = 'date'
    search_fields = ['discount_period__description_nl', 'discount_period__description_en']


class DiscountCreditAdmin(admin.ModelAdmin):
    list_display = ('id', 'discount_period', 'description', 'price', 'person', 'discount', 'date', 'added_on')
    list_filter = ('date', 'added_on', 'discount_period')
    date_hierarchy = 'date'
    search_fields = ['description', 'person__slug', 'discount_period__description_nl',
                     'discount_period__description_en']
    raw_id_fields = ('person', 'discount',)
    readonly_fields = ('added_on', 'added_by')
    ordering = ['-added_on']


class LedgerAccountAdmin(admin.ModelAdmin):
    list_display = ('id', 'name', 'ledger_account_number', 'default_statistics')
    list_editable = ('name', 'ledger_account_number', 'default_statistics')


class PrintLogAdmin(admin.ModelAdmin):
    list_display = ('id', 'actor', 'document_name', 'page_count', 'committee', 'has_transaction', 'timestamp', 'source_ip')
    list_filter = ('timestamp', 'committee', 'page_count')
    date_hierarchy = 'timestamp'
    search_fields = ['actor__first_name', 'actor__last_name', 'actor__slug', 'document_name', 'source_ip']
    raw_id_fields = ('actor', 'committee', 'transaction')
    readonly_fields = ('timestamp',)
    ordering = ['-timestamp']

    def has_transaction(self, obj):
        """Display whether the print has an associated transaction (paid print)."""
        return obj.transaction is not None
    has_transaction.boolean = True
    has_transaction.short_description = 'Paid'


admin.site.register(RFIDCard, RFIDAdmin)
admin.site.register(Transaction, TransactionAdmin)
admin.site.register(CookieCornerTransaction, CookieCornerTransactionAdmin)
admin.site.register(ActivityTransaction, ActivityTransactionAdmin)
admin.site.register(AlexiaTransaction, AlexiaTransactionAdmin)
admin.site.register(ContributionTransaction, ContributionTransactionAdmin)
admin.site.register(DebtCollectionTransaction, DebtCollectionTransactionAdmin)
admin.site.register(ReversalTransaction, ReversalTransactionAdmin)
admin.site.register(CustomTransaction, CustomTransactionAdmin)
admin.site.register(Category, CategoryAdmin)
admin.site.register(LedgerAccount, LedgerAccountAdmin)
admin.site.register(Article, ArticleAdmin)
admin.site.register(AuthorizationType, AuthorizationTypeAdmin)
admin.site.register(Authorization, AuthorizationAdmin)
admin.site.register(Amendment, AmendmentAdmin)
admin.site.register(DebtCollectionAssignment, DebtCollectionAssignmentAdmin)
admin.site.register(DebtCollectionBatch, DebtCollectionBatchAdmin)
admin.site.register(DebtCollectionInstruction, DebtCollectionInstructionAdmin)
admin.site.register(Reversal, ReversalAdmin)
admin.site.register(DiscountPeriod, DiscountPeriodAdmin)
admin.site.register(Discount, DiscountAdmin)
admin.site.register(DiscountCredit, DiscountCreditAdmin)
admin.site.register(PrintLogEntry, PrintLogAdmin)
