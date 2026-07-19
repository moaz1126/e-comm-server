from django.urls import path
from .views import ItemMovementReportView, ItemRepositoryMovementReport

urlpatterns = [
    # path('item-movement-report/', ItemMovementReportView.as_view()),
    path(
        'item-movement-json/', 
        ItemRepositoryMovementReport.as_view(), 
        {'___view_id': 'reportsWarehouse_itemMovement'},
        name='item_movement_api'
    ),
]
