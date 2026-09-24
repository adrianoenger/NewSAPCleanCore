REPORT zprogram_report.

TABLES: mara, marc.

SELECTION-SCREEN BEGIN OF BLOCK b1 WITH FRAME TITLE TEXT-001.
  SELECT-OPTIONS: so_matnr FOR mara-matnr,
                  so_werks FOR marc-werks.
  PARAMETERS: p_date TYPE sy-datum DEFAULT sy-datum.
SELECTION-SCREEN END OF BLOCK b1.

START-OF-SELECTION.

  SELECT matnr maktx FROM mara
    JOIN makt ON mara~matnr = makt~matnr
    INTO TABLE @DATA(lt_materials)
    WHERE mara~matnr IN @so_matnr
      AND makt~spras = @sy-langu.

  LOOP AT lt_materials INTO DATA(ls_material).
    WRITE: / ls_material-matnr, ls_material-maktx.
  ENDLOOP.
