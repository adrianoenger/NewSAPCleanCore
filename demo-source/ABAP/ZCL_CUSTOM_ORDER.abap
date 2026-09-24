CLASS zcl_custom_order DEFINITION
  PUBLIC
  FINAL
  CREATE PUBLIC.

  PUBLIC SECTION.
    METHODS: create_order
               IMPORTING iv_order_type TYPE string
               RETURNING VALUE(rv_order_id) TYPE string,
             process_order
               IMPORTING iv_order_id TYPE string,
             get_order_status
               IMPORTING iv_order_id TYPE string
               RETURNING VALUE(rv_status) TYPE string.

  PRIVATE SECTION.
    DATA: mv_last_order_id TYPE string.

ENDCLASS.

CLASS zcl_custom_order IMPLEMENTATION.

  METHOD create_order.
    rv_order_id = 'ORD' && sy-uzeit.
    mv_last_order_id = rv_order_id.
  ENDMETHOD.

  METHOD process_order.
    " Custom order processing logic
    " Enhancement to standard SAP order flow
  ENDMETHOD.

  METHOD get_order_status.
    rv_status = 'OPEN'.
  ENDMETHOD.

ENDCLASS.
