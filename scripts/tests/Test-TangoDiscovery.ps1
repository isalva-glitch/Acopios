# Offline regression of the actual worker functions. Never connects to Access.
$ErrorActionPreference = 'Stop'
$worker = Join-Path (Split-Path $PSScriptRoot -Parent) 'TangoAccessBridge.ps1'
$tokens=$null; $errors=$null
$ast=[System.Management.Automation.Language.Parser]::ParseFile($worker,[ref]$tokens,[ref]$errors)
if ($errors.Count) {throw 'El worker no tiene sintaxis valida.'}
foreach ($definition in $ast.FindAll({param($node) $node -is [System.Management.Automation.Language.FunctionDefinitionAst]}, $false)) {
    . ([scriptblock]::Create($definition.Extent.Text))
}
$Invariant = [Globalization.CultureInfo]::InvariantCulture
$companies = [ordered]@{FONTELA=@{Database='FONTELA_TEST'}; VIVIANA=@{Database='VIVIANA_TEST'}}
$headerFields='h.ID_GVA12'
$headerJoins=''
$script:queries = [Collections.Generic.List[string]]::new()
function Find-Pdf($row) {return $null}
function Test-Row($id,$type,$number,$amount) {
    return [pscustomobject]@{origen_id=$id;tipo=$type;numero=$number;fecha='2026-10-13';cliente='Titular diferente';cliente_codigo='TEST';total=$amount;neto_origen='19794704.51';iva='4156887.95';moneda_corriente=$true;cotizacion='1';es_anticipo=$true;estado_origen='CAN';fecha_anulacion='1800-01-01';importe_aplicado_bruto=$amount;cliente_coincide=$false}
}
function Read-Tango($db,$company,$sql) {
    $script:queries.Add($company+' '+$sql)
    if ($sql -match 'SELECT DB_NAME') {return [pscustomobject]@{database_name=$companies[$company].Database}}
    if ($company -ne 'FONTELA') {return}
    if ($script:fallback -and $sql -match 'SELECT DISTINCT TOP 6') {
        if ($sql -notmatch 'ABS\(h.IMPORTE_GR\+h.IMPORTE_EX-19794704.51\)' -or $sql -notmatch "LIKE '%MOTORPART%'") {throw 'El candidato no exige importe y obra.'}
        return [pscustomobject]@{COD_CLIENT='TEST';RAZON_SOCI='Titular diferente'}
    }
    if ($script:fallback -and $sql -match 'SELECT TOP 80') {return Test-Row 64901 FAC A0000700012371 '23951592.46'}
    if ($sql -match "WHERE h.T_COMP='FAC' AND RTRIM" -or $sql -match "WHERE h.T_COMP IN \('FAC','REC'\)") {
        return Test-Row 64901 FAC A0000700012371 '23951592.46'
    }
    if ($sql -match 'SUM\(IMPORT_CAN\) AS importe_aplicado_bruto') {
        Test-Row 1 REC E0000000045975 '12605593.47'
        Test-Row 2 REC E0000000045980 '11345998.99'
    }
}
function Assert-Receipts($result) {
    if ($result.registros.Count -ne 3) {throw 'Faltan factura o recibos.'}
    $receipts = @($result.registros | Where-Object tipo -eq REC)
    if ($receipts.Count -ne 2) {throw 'Faltan recibos aplicados.'}
    foreach ($receipt in $receipts) {
        if ($receipt.aplicaciones.Count -ne 1 -or $receipt.aplicaciones[0].factura_id -ne 64901) {throw 'Referencia de factura incorrecta.'}
    }
}
$argsTest=@{cliente='Profesional del proyecto';cuit='';obra='Obra diferente';presupuesto='215822';desde='2026-01-01';objetivos=@{FONTELA=@('19794704.51');VIVIANA=@()};facturas_confirmadas=@(@{empresa='FONTELA';numero='A0000700012371'})}
Assert-Receipts (Lookup-Tango $null $argsTest)
if (-not @($script:queries | Where-Object {$_ -match "RTRIM\(h.N_COMP\)='A0000700012371'"}).Count) {throw 'No uso la factura explicita.'}
Assert-Receipts (Lookup-Number $null @{numero_normalizado='A0000700012371';numero_modo='COMPLETO';cliente='Profesional del proyecto'})
$argsTest.facturas_confirmadas=@(@{empresa='FONTELA';numero="A0000700012371';DELETE"})
$rejected=$false
try {Lookup-Tango $null $argsTest > $null} catch {$rejected=$true}
if (-not $rejected) {throw 'Acepto una referencia invalida.'}
$script:fallback=$true
$argsTest.facturas_confirmadas=@()
$argsTest.obra='MOTORPARTS'
$result=Lookup-Tango $null $argsTest
Assert-Receipts $result
if ($result.registros[0].motivos[0] -notmatch 'titular diferente') {throw 'Oculto la diferencia de titular.'}
if (@($script:queries | Where-Object {$_ -match '^VIVIANA SELECT TOP 80'}).Count) {throw 'Consulto una empresa sin parte asignada.'}
$argsTest.objetivos.FONTELA=@()
if ((Lookup-Tango $null $argsTest).registros.Count) {throw 'Propuso candidatos sin coincidencia de importe.'}
Write-Output 'OK: factura asociada con otro titular, busqueda por numero, dos recibos, referencias e identidad validada.'