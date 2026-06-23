import sys

with open('backend/services/imputacion_service.py', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '-> Tuple[bool, Optional[str]]:',
    '-> Tuple[bool, str, Optional[str]]:'
)

content = content.replace(
    '''    # Check against acopio saldos
    is_excedente = False
    warnings = []''',
    '''    # Check against acopio saldos
    is_excedente = False
    excedente_tipo = "NONE"
    warnings = []'''
)

content = content.replace(
    '''    # If item specified, also check item saldos
    if acopio_item_id:
        item = db.query(AcopioItem).filter(AcopioItem.id == acopio_item_id).first()
        if item:
            if cantidad_m2 > item.saldo_m2:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: m2 excede saldo")
            if cantidad_ml > item.saldo_ml:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: ml excede saldo")
            if cantidad_pesos > item.saldo_pesos:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: pesos excede saldo")
            if cantidad_unidades > item.saldo_cantidad:
                is_excedente = True
                warnings.append(f"Item {item.descripcion}: unidades excede saldo")
    
    warning_msg = "; ".join(warnings) if warnings else None
    
    return is_excedente, warning_msg''',
    '''    if is_excedente:
        excedente_tipo = "ACOPIO"
        
    # If item specified, also check item saldos
    if acopio_item_id:
        item = db.query(AcopioItem).filter(AcopioItem.id == acopio_item_id).first()
        if item:
            item_excedente = False
            if cantidad_m2 > item.saldo_m2:
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: m2 excede saldo")
            if cantidad_ml > item.saldo_ml:
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: ml excede saldo")
            if cantidad_pesos > item.saldo_pesos:
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: pesos excede saldo")
            if cantidad_unidades > item.saldo_cantidad:
                item_excedente = True
                warnings.append(f"Item {item.descripcion}: unidades excede saldo")
            
            if item_excedente:
                is_excedente = True
                if excedente_tipo == "NONE":
                    excedente_tipo = "ITEM"
    
    warning_msg = "; ".join(warnings) if warnings else None
    
    return is_excedente, excedente_tipo, warning_msg'''
)

content = content.replace(
    '''    # Check for excedente
    is_excedente, warning = check_excedente(
        db, acopio_id, acopio_item_id, cantidad_m2, cantidad_ml, cantidad_pesos, cantidad_unidades
    )''',
    '''    # Check for excedente
    is_excedente, excedente_tipo, warning = check_excedente(
        db, acopio_id, acopio_item_id, cantidad_m2, cantidad_ml, cantidad_pesos, cantidad_unidades
    )'''
)

content = content.replace(
    '''        es_excedente=is_excedente,
        pedido_item_descripcion=pedido_item_descripcion,''',
    '''        es_excedente=is_excedente,
        excedente_tipo=excedente_tipo if is_excedente else "NONE",
        excedente_motivo=warning if is_excedente else None,
        pedido_item_descripcion=pedido_item_descripcion,'''
)

content = content.replace(
    '''    warnings: list[str] = []
    excedente_flags: list[bool] = []

    def to_decimal(value) -> Decimal:''',
    '''    warnings: list[str] = []
    excedente_flags: list[bool] = []
    excedente_tipos: list[str] = []
    excedente_motivos: list[str] = []

    def to_decimal(value) -> Decimal:'''
)

content = content.replace(
    '''    def mark_excedente(indices: list[int], message: str) -> None:
        for index in indices:
            excedente_flags[index] = True
        add_warning(message)''',
    '''    def mark_excedente(indices: list[int], message: str, tipo: str) -> None:
        for index in indices:
            excedente_flags[index] = True
            if excedente_tipos[index] == "NONE" or (excedente_tipos[index] == "ITEM" and tipo == "ACOPIO"):
                excedente_tipos[index] = tipo
            
            # Append reason
            current_motivos = excedente_motivos[index].split("; ") if excedente_motivos[index] else []
            if message not in current_motivos:
                current_motivos.append(message)
                excedente_motivos[index] = "; ".join(current_motivos)
                
        add_warning(message)'''
)

content = content.replace(
    '''    for consumo in consumos:
        is_excedente, warning = check_excedente(
            db,
            consumo["acopio_id"],
            consumo.get("acopio_item_id"),
            consumo["cantidad_m2"],
            consumo["cantidad_ml"],
            consumo["cantidad_pesos"],
            consumo["cantidad_unidades"],
        )
        excedente_flags.append(is_excedente)
        add_warning(warning)''',
    '''    for consumo in consumos:
        is_excedente, excedente_tipo, warning = check_excedente(
            db,
            consumo["acopio_id"],
            consumo.get("acopio_item_id"),
            consumo["cantidad_m2"],
            consumo["cantidad_ml"],
            consumo["cantidad_pesos"],
            consumo["cantidad_unidades"],
        )
        excedente_flags.append(is_excedente)
        excedente_tipos.append(excedente_tipo if is_excedente else "NONE")
        excedente_motivos.append(warning if is_excedente else "")
        add_warning(warning)'''
)

content = content.replace(
    '''        if bucket["m2"] > to_decimal(acopio.saldo_m2):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado m2 {bucket['m2']} excede saldo {acopio.saldo_m2}",
            )
        if bucket["ml"] > to_decimal(acopio.saldo_ml):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado ml {bucket['ml']} excede saldo {acopio.saldo_ml}",
            )
        if bucket["pesos"] > to_decimal(acopio.saldo_pesos):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado pesos {bucket['pesos']} excede saldo {acopio.saldo_pesos}",
            )
        if bucket["unidades"] > int(acopio.saldo_unidades or 0):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado unidades {bucket['unidades']} excede saldo {acopio.saldo_unidades}",
            )''',
    '''        if bucket["m2"] > to_decimal(acopio.saldo_m2):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado m2 {bucket['m2']} excede saldo {acopio.saldo_m2}",
                "ACOPIO"
            )
        if bucket["ml"] > to_decimal(acopio.saldo_ml):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado ml {bucket['ml']} excede saldo {acopio.saldo_ml}",
                "ACOPIO"
            )
        if bucket["pesos"] > to_decimal(acopio.saldo_pesos):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado pesos {bucket['pesos']} excede saldo {acopio.saldo_pesos}",
                "ACOPIO"
            )
        if bucket["unidades"] > int(acopio.saldo_unidades or 0):
            mark_excedente(
                bucket["indices"],
                f"Acopio {acopio_id}: consumo acumulado unidades {bucket['unidades']} excede saldo {acopio.saldo_unidades}",
                "ACOPIO"
            )'''
)

content = content.replace(
    '''        if bucket["m2"] > to_decimal(item.saldo_m2):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado m2 {bucket['m2']} excede saldo {item.saldo_m2}",
            )
        if bucket["ml"] > to_decimal(item.saldo_ml):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado ml {bucket['ml']} excede saldo {item.saldo_ml}",
            )
        if bucket["pesos"] > to_decimal(item.saldo_pesos):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado pesos {bucket['pesos']} excede saldo {item.saldo_pesos}",
            )
        if bucket["unidades"] > int(item.saldo_cantidad or 0):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado unidades {bucket['unidades']} excede saldo {item.saldo_cantidad}",
            )''',
    '''        if bucket["m2"] > to_decimal(item.saldo_m2):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado m2 {bucket['m2']} excede saldo {item.saldo_m2}",
                "ITEM"
            )
        if bucket["ml"] > to_decimal(item.saldo_ml):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado ml {bucket['ml']} excede saldo {item.saldo_ml}",
                "ITEM"
            )
        if bucket["pesos"] > to_decimal(item.saldo_pesos):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado pesos {bucket['pesos']} excede saldo {item.saldo_pesos}",
                "ITEM"
            )
        if bucket["unidades"] > int(item.saldo_cantidad or 0):
            mark_excedente(
                bucket["indices"],
                f"Item {item_label}: consumo acumulado unidades {bucket['unidades']} excede saldo {item.saldo_cantidad}",
                "ITEM"
            )'''
)

content = content.replace(
    '''    imputaciones: list[Imputacion] = []
    for consumo, is_excedente in zip(consumos, excedente_flags):
        imputacion = Imputacion(
            pedido_id=consumo["pedido_id"],
            acopio_id=consumo["acopio_id"],
            acopio_item_id=consumo.get("acopio_item_id"),
            cantidad_m2=consumo["cantidad_m2"],
            cantidad_ml=consumo["cantidad_ml"],
            cantidad_pesos=consumo["cantidad_pesos"],
            cantidad_unidades=consumo["cantidad_unidades"],
            es_excedente=is_excedente,
            pedido_item_descripcion=consumo.get("pedido_item_descripcion"),''',
    '''    imputaciones: list[Imputacion] = []
    for i, consumo in enumerate(consumos):
        is_excedente = excedente_flags[i]
        imputacion = Imputacion(
            pedido_id=consumo["pedido_id"],
            acopio_id=consumo["acopio_id"],
            acopio_item_id=consumo.get("acopio_item_id"),
            cantidad_m2=consumo["cantidad_m2"],
            cantidad_ml=consumo["cantidad_ml"],
            cantidad_pesos=consumo["cantidad_pesos"],
            cantidad_unidades=consumo["cantidad_unidades"],
            es_excedente=is_excedente,
            excedente_tipo=excedente_tipos[i],
            excedente_motivo=excedente_motivos[i] if is_excedente and excedente_motivos[i] else None,
            pedido_item_descripcion=consumo.get("pedido_item_descripcion"),'''
)

with open('backend/services/imputacion_service.py', 'w', encoding='utf-8') as f:
    f.write(content)
