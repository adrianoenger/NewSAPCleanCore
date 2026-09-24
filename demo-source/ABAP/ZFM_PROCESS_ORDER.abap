FUNCTION zfm_process_order.
*"----------------------------------------------------------------------
*"*"Local Interface:
*"  IMPORTING
*"     VALUE(IV_ORDER_ID) TYPE  STRING
*"     VALUE(IV_ACTION)   TYPE  STRING
*"  EXPORTING
*"     VALUE(EV_STATUS)   TYPE  STRING
*"     VALUE(EV_MESSAGE)  TYPE  STRING
*"----------------------------------------------------------------------

  DATA: lv_order TYPE string.

  " Read order header
  SELECT SINGLE matnr aufnr
    FROM aufk
    INTO @DATA(ls_order)
    WHERE aufnr = @iv_order_id.

  IF sy-subrc = 0.
    ev_status = 'FOUND'.
    ev_message = 'Order processed successfully'.
  ELSE.
    ev_status = 'NOT_FOUND'.
    ev_message = 'Order not found'.
  ENDIF.

ENDFUNCTION.
