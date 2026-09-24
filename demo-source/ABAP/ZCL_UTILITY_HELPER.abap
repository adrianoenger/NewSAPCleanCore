CLASS zcl_utility_helper DEFINITION
  PUBLIC
  FINAL
  CREATE PUBLIC.

  PUBLIC SECTION.
    CLASS-METHODS:
      format_date
        IMPORTING iv_date TYPE d
        RETURNING VALUE(rv_formatted) TYPE string,
      validate_input
        IMPORTING iv_value TYPE string
        RETURNING VALUE(rv_valid) TYPE abap_bool.

ENDCLASS.

CLASS zcl_utility_helper IMPLEMENTATION.

  METHOD format_date.
    rv_formatted = iv_date+6(2) && '.' && iv_date+4(2) && '.' && iv_date(4).
  ENDMETHOD.

  METHOD validate_input.
    rv_valid = xsdbool( iv_value IS NOT INITIAL AND strlen( iv_value ) > 0 ).
  ENDMETHOD.

ENDCLASS.
