param(
    [string]$BridgeRoot = (Join-Path (Split-Path $PSScriptRoot -Parent) 'backend\.tango_access_bridge'),
    [string]$AccessFile = 'C:\Users\windows\Desktop\Interfaz TANGO FONTELA Version2 SEPARACION FAC REM.mdb',
    [switch]$Once
)
# Run in Windows PowerShell or PowerShell 7 STA. Only fixed SELECT queries are exposed.
# Bind only an existing Access session via the standard Windows ROT API.
if (-not ('TangoAccessRunningObject' -as [type])) {
    Add-Type -TypeDefinition @"
using System;
using System.Runtime.InteropServices;
public static class TangoAccessRunningObject {
    [DllImport("ole32.dll", CharSet=CharSet.Unicode, PreserveSig=false)]
    private static extern void CLSIDFromProgID(string progid, out Guid clsid);
    [DllImport("oleaut32.dll", PreserveSig=false)]
    private static extern void GetActiveObject(ref Guid clsid, IntPtr reserved,
        [MarshalAs(UnmanagedType.IUnknown)] out object app);
    public static object Get() {
        Guid id; CLSIDFromProgID("Access.Application", out id);
        object app; GetActiveObject(ref id, IntPtr.Zero, out app); return app;
    }
}
"@
}
$ErrorActionPreference = 'Stop'
$Invariant = [Globalization.CultureInfo]::InvariantCulture
$BridgeRoot = [IO.Path]::GetFullPath($BridgeRoot)
$requests = Join-Path $BridgeRoot 'requests'
$responses = Join-Path $BridgeRoot 'responses'
[void][IO.Directory]::CreateDirectory($requests)
[void][IO.Directory]::CreateDirectory($responses)
try { $workerLock = [IO.File]::Open((Join-Path $BridgeRoot 'worker.lock'), 'OpenOrCreate', 'ReadWrite', 'None') }
catch { throw 'Ya hay un conector Access ejecutándose.' }
$companies = [ordered]@{
    FONTELA = @{Link='GVA14';Database='JOSE_M_FONTELA_E_HIJOS_SACIF'}
    VIVIANA = @{Link='B_GVA14';Database='VIVIANA_FONTELA_NUEVA'}
}
$allowedPdfRoot = '\\srvfontela\SYSGESTION\RECIBOS'
function Write-AtomicJson($path, $value) {
    $temp = $path + '.tmp'
    [IO.File]::WriteAllText($temp, ($value | ConvertTo-Json -Compress -Depth 20), [Text.UTF8Encoding]::new($false))
    Move-Item -LiteralPath $temp -Destination $path -Force
}
function Sql-Literal([string]$value) { return "'" + $value.Replace("'", "''") + "'" }
function Sql-Like([string]$value) {
    return Sql-Literal ('%' + $value.Replace('[','[[]').Replace('%','[%]').Replace('_','[_]') + '%')
}
function Money($value) {
    if ($null -eq $value -or $value -is [DBNull]) { return [decimal]0 }
    $number = if ($value -is [string]) {[decimal]::Parse($value, $Invariant)} else {[decimal]$value}
    return [decimal]::Round($number, 2, [MidpointRounding]::AwayFromZero)
}
function Money-Text($value) { return (Money $value).ToString('0.00', $Invariant) }
function Normalize-Name([string]$value) {
    $decomposed = $value.Normalize([Text.NormalizationForm]::FormD)
    $plain = [regex]::Replace($decomposed, '\p{M}', '')
    return ([regex]::Replace($plain.ToUpperInvariant(), '[^\p{L}\p{N}]', ''))
}
function Read-Tango($db, [string]$company, [string]$sql) {
    if (-not $companies.Contains($company) -or $sql -notmatch '^\s*SELECT\b') { throw 'Consulta no permitida.' }
    $q = $null; $rs = $null
    try {
        $q = $db.CreateQueryDef('')
        $q.Connect = $db.TableDefs.Item($companies[$company].Link).Connect
        $q.ReturnsRecords = $true
        $q.ODBCTimeout = 8
        $q.SQL = $sql
        $rs = $q.OpenRecordset(4, 4) # snapshot, read only
        $items = [Collections.Generic.List[object]]::new()
        while (-not $rs.EOF) {
            $item = [ordered]@{}
            for ($i = 0; $i -lt $rs.Fields.Count; $i++) {
                $field = $rs.Fields.Item($i)
                $item[$field.Name] = if ($field.Value -is [DBNull]) {$null} else {$field.Value}
            }
            $items.Add([pscustomobject]$item)
            if ($items.Count -gt 200) { throw 'Respuesta demasiado extensa.' }
            $rs.MoveNext()
        }
        return $items.ToArray()
    } finally {
        if ($rs) { $rs.Close(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($rs) }
        if ($q) { $q.Close(); [void][Runtime.InteropServices.Marshal]::ReleaseComObject($q) }
    }
}
function Find-Pdf($row) {
    if (-not $row.pdf_root -or $row.numero -notmatch '^[A-Za-z0-9 ]{1,30}$' -or $row.tipo -notmatch '^[A-Z]{2,5}$') { return $null }
    $root = [IO.Path]::GetFullPath([string]$row.pdf_root).TrimEnd('\')
    if ($root -ne $allowedPdfRoot) { return $null }
    $stem = ([string]$row.tipo).Trim() + ([string]$row.numero).Trim()
    $file = Join-Path (Join-Path $root $stem) ($stem + '.pdf')
    if ([IO.File]::Exists($file) -and ([IO.FileInfo]$file).Length -le 20MB) { return $file }
    return $null
}
$headerFields = @"
h.ID_GVA12 AS origen_id,h.T_COMP AS tipo,h.N_COMP AS numero,
CONVERT(varchar(10),h.FECHA_EMIS,23) AS fecha,h.COD_CLIENT AS cliente_codigo,
c.RAZON_SOCI AS cliente,h.IMPORTE AS total,h.IMPORTE_GR+h.IMPORTE_EX AS neto_origen,
h.IMPORTE_IV AS iva,h.MON_CTE AS moneda_corriente,h.COTIZ AS cotizacion,
h.ESTADO AS estado_origen,CONVERT(varchar(10),h.FECHA_ANU,23) AS fecha_anulacion,
h.LEYENDA_1,h.LEYENDA_2,h.OBSERVAC AS observacion,t.PATH_PDF AS pdf_root,
CASE WHEN EXISTS(SELECT 1 FROM dbo.GVA53 l WHERE l.T_COMP=h.T_COMP AND l.N_COMP=h.N_COMP
                 AND l.COD_ARTICU IN ('ANTI','000000000000007')) THEN 1 ELSE 0 END AS es_anticipo
"@
$headerJoins = "LEFT JOIN dbo.GVA14 c ON c.COD_CLIENT=h.COD_CLIENT LEFT JOIN dbo.GVA43 t ON t.TALONARIO=h.TALONARIO"
function New-Record($row, [string]$company, [string[]]$motives) {
    $control = if ($company -eq 'VIVIANA') {$row.total} else {$row.neto_origen}
    if ($row.tipo -eq 'REC') { $control = $null } # receipts have a gross original, not a net original
    return [ordered]@{
        empresa=$company; origen_id=[int]$row.origen_id; tipo=([string]$row.tipo).Trim()
        numero=([string]$row.numero).Trim(); fecha=$row.fecha; cliente=$row.cliente
        cliente_codigo=([string]$row.cliente_codigo).Trim(); total=(Money-Text $row.total)
        importe_control=if ($null -eq $control) {'0.00'} else {Money-Text $control}
        neto_origen=(Money-Text $row.neto_origen); iva=(Money-Text $row.iva)
        moneda_corriente=[bool]$row.moneda_corriente; cotizacion=[string]$row.cotizacion
        es_anticipo=[bool]$row.es_anticipo; estado_origen=$row.estado_origen; fecha_anulacion=$row.fecha_anulacion
        motivos=@($motives); aplicaciones=@(); referencias_pedido=@()
        pdf_disponible=[bool](Find-Pdf $row)
        observacion=(([string]$row.LEYENDA_1 + ' ' + [string]$row.LEYENDA_2 + ' ' + [string]$row.observacion).Trim())
        base_importe=if ($row.tipo -eq 'REC') {'Importe original bruto; revisar sus aplicaciones.'} elseif ($company -eq 'VIVIANA') {'Importe interno Viviana.'} else {'Neto gravado más exento, sin IVA.'}
    }
}
function Add-ReceiptContext($db, $documents) {
    # A receipt can cover other invoices. Obtain the complete application context
    # to calculate its original net equivalent before allowing manual association.
    foreach ($document in @($documents.Values)) {
        if ($document.tipo -ne 'REC' -or $document.empresa -ne 'FONTELA') { continue }
        $receiptNumber = Sql-Literal $document.numero
        $clientCode = Sql-Literal $document.cliente_codigo
        $context = @(Read-Tango $db 'FONTELA' @"
SELECT TOP 201 b.ID_GVA12 AS factura_id,b.N_COMP AS factura_numero,
b.IMPORTE AS factura_total,b.IMPORTE_GR+b.IMPORTE_EX AS factura_neto,
b.MON_CTE AS factura_moneda,CONVERT(varchar(10),b.FECHA_ANU,23) AS factura_anulacion,
h.ID_GVA12 AS origen_id,h.T_COMP AS tipo,h.N_COMP AS numero,h.IMPORTE AS total,
h.IMPORTE_GR+h.IMPORTE_EX AS neto,h.MON_CTE AS moneda_corriente,
CONVERT(varchar(10),h.FECHA_ANU,23) AS fecha_anulacion,i.aplicado
FROM (SELECT T_COMP,N_COMP,T_COMP_CAN,N_COMP_CAN,SUM(IMPORT_CAN) AS aplicado
      FROM dbo.GVA07 WHERE T_COMP='FAC' AND (T_COMP_CAN='REC' OR T_COMP_CAN LIKE 'NC%')
      GROUP BY T_COMP,N_COMP,T_COMP_CAN,N_COMP_CAN) i
JOIN dbo.GVA12 b ON b.T_COMP=i.T_COMP AND b.N_COMP=i.N_COMP AND b.COD_CLIENT=$clientCode
JOIN dbo.GVA12 h ON h.T_COMP=i.T_COMP_CAN AND h.N_COMP=i.N_COMP_CAN AND h.COD_CLIENT=$clientCode
WHERE EXISTS(SELECT 1 FROM dbo.GVA07 own WHERE own.T_COMP=b.T_COMP AND own.N_COMP=b.N_COMP
             AND own.T_COMP_CAN='REC' AND own.N_COMP_CAN=$receiptNumber)
ORDER BY b.ID_GVA12,h.FECHA_EMIS,h.ID_GVA12
"@)
        $document.contexto_neto = @($context)
    }
}
function Add-InvoiceContext($db, $documents) {
    foreach ($invoice in @($documents.Values)) {
        if ($invoice.tipo -ne 'FAC') {continue}
        $company = $invoice.empresa
        $id = [int]$invoice.origen_id
        $number = Sql-Literal $invoice.numero
        $code = Sql-Literal $invoice.cliente_codigo
            $apps = @(Read-Tango $db $company @"
SELECT TOP 101 $headerFields,i.importe_aplicado_bruto
FROM (SELECT T_COMP_CAN,N_COMP_CAN,SUM(IMPORT_CAN) AS importe_aplicado_bruto
      FROM dbo.GVA07 WHERE T_COMP='FAC' AND N_COMP=$number
      AND (T_COMP_CAN='REC' OR T_COMP_CAN LIKE 'NC%')
      GROUP BY T_COMP_CAN,N_COMP_CAN) i
JOIN dbo.GVA12 h ON h.T_COMP=i.T_COMP_CAN AND h.N_COMP=i.N_COMP_CAN AND h.COD_CLIENT=$code
$headerJoins
ORDER BY h.FECHA_EMIS,h.ID_GVA12
"@)
            if ($apps.Count -gt 100) { throw 'El anticipo tiene demasiadas aplicaciones para esta consulta.' }
            foreach ($application in $apps) {
                $appType = ([string]$application.tipo).Trim()
                $appId = [int]$application.origen_id
                $appKey = "$company|$appType|$appId"
                if (-not $documents.Contains($appKey)) {
                    $documents[$appKey] = New-Record $application $company @('Aplicado en Tango a una factura candidata.')
                }
                $documents[$appKey].aplicaciones += [ordered]@{factura_id=$id;factura_numero=$invoice.numero;importe_bruto=(Money-Text $application.importe_aplicado_bruto)}
            }
            $orders = @(Read-Tango $db $company @"
SELECT TOP 6 p.ID_GVA21,p.NRO_PEDIDO,p.TALON_PED,p.NRO_OC_COMP,p.LEYENDA_1,p.LEYENDA_2,p.TOTAL_PEDI
FROM dbo.GVA55 g JOIN dbo.GVA21 p ON p.NRO_PEDIDO=g.NRO_PEDIDO AND p.TALON_PED=g.TALON_PED AND p.COD_CLIENT=$code
WHERE g.T_COMP='FAC' AND g.N_COMP=$number ORDER BY p.ID_GVA21
"@)
            $invoice.referencias_pedido = @($orders | ForEach-Object {[ordered]@{id=[int]$_.ID_GVA21;pedido=([string]$_.NRO_PEDIDO).Trim();oc=$_.NRO_OC_COMP;obra=$_.LEYENDA_1;importe=(Money-Text $_.TOTAL_PEDI)}})
    }
}
function Lookup-Number($db, $arguments) {
    $digits = [string]$arguments.numero_normalizado
    if ($digits -notmatch '^[A-Z]?[0-9]{1,13}$') { throw 'Número de comprobante no válido.' }
    $mode = [string]$arguments.numero_modo
    $numberWhere = switch ($mode) {
        'SECUENCIA' {"RIGHT(RTRIM(h.N_COMP),8)=" + (Sql-Literal $digits.PadLeft(8,'0'))}
        'SIN_LETRA' {"RIGHT(RTRIM(h.N_COMP),13)=" + (Sql-Literal $digits)}
        'COMPLETO' {"RTRIM(h.N_COMP)=" + (Sql-Literal $digits)}
        default {throw 'Formato de número no válido.'}
    }
    $documents = [ordered]@{}
    $notices = [Collections.Generic.List[string]]::new()
    $customerWords = @([regex]::Matches(([string]$arguments.cliente).ToUpperInvariant(), '[\p{L}\p{N}]+') | ForEach-Object {$_.Value} | Where-Object {$_.Length -gt 1 -and $_ -notin @('SA','SAS','SRL','SACIF','DE','DEL','LA','EL','LOS','LAS','HIJOS')} | Select-Object -First 4)
    $customerWhere = if($customerWords.Count) {'(' + (@($customerWords | ForEach-Object {"c.RAZON_SOCI COLLATE Latin1_General_CI_AI LIKE " + (Sql-Like $_)}) -join ' AND ') + ')'} else {'1=0'}
    $cuit = [regex]::Replace([string]$arguments.cuit,'\D','')
    if($cuit.Length -eq 11){$customerWhere="REPLACE(REPLACE(c.CUIT,'-',''),' ','')=" + (Sql-Literal $cuit) + " OR " + $customerWhere}
    foreach($company in $companies.Keys) {
        $check = @(Read-Tango $db $company 'SELECT DB_NAME() AS database_name')
        if($check[0].database_name -ne $companies[$company].Database){throw 'El vínculo Access apunta a otra empresa.'}
        $rows = @(Read-Tango $db $company @"
SELECT TOP 11 $headerFields,
CASE WHEN ($customerWhere) THEN 1 ELSE 0 END AS cliente_coincide
FROM dbo.GVA12 h $headerJoins
WHERE h.T_COMP IN ('FAC','REC') AND ($numberWhere)
ORDER BY h.FECHA_EMIS DESC,h.ID_GVA12 DESC
"@)
        if($rows.Count -gt 10){$notices.Add("Hay más de diez coincidencias en $company. Completá letra y punto de venta.")}
        foreach($row in @($rows | Select-Object -First 10)) {
            $record = New-Record $row $company @('Coincide el número ingresado; revisar cliente y aplicación al acopio.')
            $record.busqueda_numero = $true
            $record.cliente_coincide = [bool]$row.cliente_coincide
            $record.es_anticipo = [bool]$row.es_anticipo
            if(-not $record.cliente_coincide){$record.motivos += 'El nombre del cliente en Tango no coincide exactamente con el del acopio.'}
            $documents["$company|$($record.tipo)|$($record.origen_id)"] = $record
        }
    }
    Add-InvoiceContext $db $documents
    Add-ReceiptContext $db $documents
    return @{registros=@($documents.Values);avisos=@($notices.ToArray())}
}
function Lookup-Tango($db, $arguments) {
    if ($arguments.numero_normalizado) {return Lookup-Number $db $arguments}

    $customer = [string]$arguments.cliente
    if ($customer.Length -gt 200 -or $customer.Length -lt 2) { throw 'Cliente no válido.' }
    $words = @([regex]::Matches($customer.ToUpperInvariant(), '[\p{L}\p{N}]+') | ForEach-Object {$_.Value} | Where-Object { $_.Length -gt 1 -and $_ -notin @('SA','SAS','SRL','SACIF','DE','DEL','LA','EL','LOS','LAS','HIJOS') } | Select-Object -First 4)
    $cuit = [regex]::Replace([string]$arguments.cuit, '\D', '')
    if (-not $words.Count -and $cuit.Length -ne 11) { throw 'El nombre del cliente no permite una búsqueda precisa.' }
    $nameParts = @($words | ForEach-Object {"RAZON_SOCI COLLATE Latin1_General_CI_AI LIKE " + (Sql-Like $_)})
    $nameWhere = if ($nameParts.Count) {'(' + ($nameParts -join ' AND ') + ')'} else {'1=0'}
    if ($cuit.Length -eq 11) { $nameWhere = "REPLACE(REPLACE(CUIT,'-',''),' ','')=" + (Sql-Literal $cuit) + " OR " + $nameWhere }
    $date = [datetime]::ParseExact([string]$arguments.desde, 'yyyy-MM-dd', $Invariant).ToString('yyyyMMdd')
    $project = Normalize-Name ([string]$arguments.obra)
    $budget = ([string]$arguments.presupuesto).TrimStart('0')
    $documents = [ordered]@{}
    $notices = [Collections.Generic.List[string]]::new()
    $foundCustomers = 0
    # Only explicit active associations of THIS acopio supply known invoice identities.
    $confirmed = @($arguments.facturas_confirmadas)
    if ($confirmed.Count -gt 20) {throw 'Demasiadas facturas asociadas para esta consulta.'}
    foreach ($known in $confirmed) {
        if ($null -eq $known) {continue}
        $company = [string]$known.empresa
        $number = [string]$known.numero
        if (-not $companies.Contains($company) -or $number -notmatch '^[A-Z][0-9]{13}$') {throw 'Referencia de factura no valida.'}
        $check = @(Read-Tango $db $company 'SELECT DB_NAME() AS database_name')
        if ($check[0].database_name -ne $companies[$company].Database) {throw 'El vinculo Access apunta a otra empresa.'}
        $literal = Sql-Literal $number
        $rows = @(Read-Tango $db $company "SELECT TOP 2 $headerFields FROM dbo.GVA12 h $headerJoins WHERE h.T_COMP='FAC' AND RTRIM(h.N_COMP)=$literal")
        if ($rows.Count -gt 1) {throw 'La factura asociada no tiene una identidad unica en Tango.'}
        if (-not $rows.Count) {$notices.Add("No se encontro en $company la factura asociada $number."); continue}
        $invoice = $rows[0]
        $key = "$company|FAC|$([int]$invoice.origen_id)"
        $documents[$key] = New-Record $invoice $company @('Factura ya asociada a este acopio: se recuperan sus aplicaciones en Tango aunque el titular facturado sea diferente.')
    }
    foreach ($company in $companies.Keys) {
        $check = @(Read-Tango $db $company 'SELECT DB_NAME() AS database_name')
        if ($check[0].database_name -ne $companies[$company].Database) { throw 'El enlace Access apunta a otra empresa. Revisá sus vínculos.' }
        $targets = @($arguments.objetivos.$company | ForEach-Object {Money $_} | Where-Object {$_ -gt 0})
        if (-not $targets.Count -and -not $arguments.ampliar) {continue}
        $controlSql = if ($company -eq 'VIVIANA') {'h.IMPORTE'} else {'h.IMPORTE_GR+h.IMPORTE_EX'}
        $amountSql = if ($targets.Count) {(@($targets | ForEach-Object {"ABS($controlSql-" + $_.ToString('0.00',$Invariant) + ")<=0.01"}) -join ' OR ')} else {'1=0'}
        $customers = @(Read-Tango $db $company ("SELECT TOP 6 COD_CLIENT,RAZON_SOCI FROM dbo.GVA14 WHERE " + $nameWhere + " ORDER BY COD_CLIENT"))
        $projectCustomer = $false
        # For an unknown fiscal payer, require BOTH the exact net and a meaningful
        # project token in its legal name. This only proposes reviewable candidates.
        if (-not $customers.Count -and $targets.Count) {
            $projectWords = @([regex]::Matches(([string]$arguments.obra).ToUpperInvariant(), '[\p{L}\p{N}]+') | ForEach-Object {$_.Value} | Where-Object {$_.Length -ge 7 -and $_ -notin @('GENERAL','GENERICA','GENERICO','PROYECTO','PRESUPUESTO','CRISTALES','ABERTURAS')} | Select-Object -First 3)
            if ($projectWords.Count) {
                $projectParts = @($projectWords | ForEach-Object {
                    $word = if ($_.Length -ge 8 -and $_.EndsWith('S')) {$_.Substring(0,$_.Length-1)} else {$_}
                    "c.RAZON_SOCI COLLATE Latin1_General_CI_AI LIKE " + (Sql-Like $word)
                })
                $projectWhere = '(' + ($projectParts -join ' AND ') + ')'
                $customers = @(Read-Tango $db $company "SELECT DISTINCT TOP 6 c.COD_CLIENT,c.RAZON_SOCI FROM dbo.GVA14 c JOIN dbo.GVA12 h ON h.COD_CLIENT=c.COD_CLIENT WHERE h.T_COMP='FAC' AND h.FECHA_EMIS>='$date' AND ($amountSql) AND $projectWhere ORDER BY c.COD_CLIENT")
                $projectCustomer = $customers.Count -gt 0
            }
        }
        if (-not $customers.Count) { $notices.Add("No se encontró el cliente por nombre, CUIT o referencia de obra en $company; se revisan también las facturas ya asociadas."); continue }
        $foundCustomers += $customers.Count
        if ($customers.Count -gt 1) { $notices.Add("Hay varios clientes posibles en $company. Revisá el cliente indicado en cada registro.") }
        $codes = (@($customers | ForEach-Object {Sql-Literal $_.COD_CLIENT}) -join ',')
        $sql = @"
SELECT TOP 80 $headerFields
FROM dbo.GVA12 h $headerJoins
WHERE h.COD_CLIENT IN ($codes) AND h.T_COMP='FAC' AND h.FECHA_EMIS>='$date'


ORDER BY CASE WHEN ($amountSql) THEN 0 ELSE 1 END,h.FECHA_EMIS DESC,h.ID_GVA12 DESC
"@
        $invoices = @(Read-Tango $db $company $sql)
        $selected = 0
        foreach ($invoice in $invoices) {
            $motives = [Collections.Generic.List[string]]::new()
            $control = if ($company -eq 'VIVIANA') {Money $invoice.total} else {Money $invoice.neto_origen}
            if (@($targets | Where-Object {[math]::Abs($_ - $control) -le 0.01}).Count) { if ($projectCustomer) {$motives.Add('Coinciden el importe y la referencia de obra con la razon social en Tango; titular diferente: revisar.')} else {$motives.Add('Coincide cliente e importe del acopio o de su parte.')} }
            $reference = Normalize-Name (([string]$invoice.LEYENDA_1)+' '+([string]$invoice.LEYENDA_2)+' '+([string]$invoice.observacion))
            if ($project.Length -ge 6 -and $project -ne 'GENERAL' -and $reference.Contains($project)) { $motives.Add('La referencia coincide con la obra.') }
            if ($budget.Length -ge 5 -and $reference.Contains($budget)) { $motives.Add('La referencia contiene el número de presupuesto.') }
            if (-not $motives.Count) {
                if (-not $arguments.ampliar) { continue }
                $motives.Add('Solo coincide el cliente: revisar antes de conservar.')
            }
            if ($selected -ge 6) { $notices.Add("Se muestran hasta seis facturas candidatas por empresa. Acotá la búsqueda con los datos del acopio."); break }
            $selected++
            $id = [int]$invoice.origen_id
            $number = Sql-Literal $invoice.numero
            $code = Sql-Literal $invoice.cliente_codigo
            $key = "$company|FAC|$id"
            if ($documents.Contains($key)) {continue}
            $record = New-Record $invoice $company $motives.ToArray()
            $documents[$key] = $record

        }
        if ($company -eq 'VIVIANA') {
            $receiptAmountSql = if ($targets.Count) {(@($targets | ForEach-Object {"ABS(h.IMPORTE-" + $_.ToString('0.00',$Invariant) + ")<=0.01"}) -join ' OR ')} else {'1=0'}
            $extra = if ($arguments.ampliar) {''} else {" AND ($receiptAmountSql)"}
            $receipts = @(Read-Tango $db $company @"
SELECT TOP 6 $headerFields FROM dbo.GVA12 h $headerJoins
WHERE h.COD_CLIENT IN ($codes) AND h.T_COMP='REC' AND h.ESTADO='CTA'
AND h.FECHA_EMIS>='$date'  $extra
ORDER BY h.FECHA_EMIS DESC,h.ID_GVA12 DESC
"@)
            foreach ($receipt in $receipts) {
                $rKey = "$company|REC|$([int]$receipt.origen_id)"
                if (-not $documents.Contains($rKey)) {
                    $r = New-Record $receipt $company @('Recibo Viviana a cuenta: revisar la asignación al acopio.')
                    $r.importe_control = Money-Text $receipt.total
                    $r.base_importe = 'Viviana: recibo a cuenta. La asignación al acopio está pendiente de revisión.'
                    $documents[$rKey] = $r
                }
            }
        }
    }

    Add-InvoiceContext $db $documents
    Add-ReceiptContext $db $documents
    if (-not $foundCustomers) { $notices.Add('Revisá el nombre o CUIT del cliente del acopio; no se hallaron coincidencias en Tango.') }
    if (-not $documents.Count) { $notices.Add('No hay coincidencias precisas. Podés ampliar la búsqueda por cliente.') }
    if ($documents.Count -gt 120) { throw 'Demasiados comprobantes relacionados. Revisá los datos del acopio.' }
    $notices.Add('Conservar datos en este panel no crea comprobantes manuales ni modifica consumos o saldos.')
    return @{registros=@($documents.Values);avisos=@($notices.ToArray())}
}
$lastHeartbeat = [datetime]::MinValue
try {
    Write-AtomicJson (Join-Path $BridgeRoot 'worker.json') @{pid=$PID;version=1}
    do {
        if (Test-Path -LiteralPath (Join-Path $BridgeRoot 'stop')) { break }
        if (([datetime]::UtcNow - $lastHeartbeat).TotalSeconds -ge 4) {
            $open = $false; $app = $null
            try { $app=[TangoAccessRunningObject]::Get(); $open=([IO.Path]::GetFullPath($app.CurrentProject.FullName) -eq [IO.Path]::GetFullPath($AccessFile)) } catch {}
            finally { if ($app) {[void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)} }
            Write-AtomicJson (Join-Path $BridgeRoot 'heartbeat.json') @{version=1;utc=[DateTimeOffset]::UtcNow.ToUnixTimeSeconds();access=$open}
            $lastHeartbeat = [datetime]::UtcNow
        }
        $jobs = @(Get-ChildItem -LiteralPath $requests -Filter '*.json' -File | Sort-Object Name | Select-Object -First 1)
        foreach ($job in $jobs) {
            $app=$null; $db=$null; $packet=$null
            try {
                $request = [IO.File]::ReadAllText($job.FullName) | ConvertFrom-Json
                if ($request.version -ne 1 -or $request.id -notmatch '^[a-f0-9]{32}$' -or $job.BaseName -ne $request.id) { throw 'Solicitud no válida.' }
                if ([double]$request.expires -lt [DateTimeOffset]::UtcNow.ToUnixTimeSeconds()) { throw 'La consulta expiró; volvé a intentar.' }
                $app=[TangoAccessRunningObject]::Get()
                if ([IO.Path]::GetFullPath($app.CurrentProject.FullName) -ne [IO.Path]::GetFullPath($AccessFile)) { throw 'Abrí la interfaz Access de Tango configurada.' }
                $db=$app.CurrentDb()
                if ($request.operation -eq 'lookup') {
                    $data=Lookup-Tango $db $request.arguments
                    $packet=@{version=1;id=$request.id;ok=$true;data=$data}
                } elseif ($request.operation -eq 'pdf') {
                    $company=[string]$request.arguments.empresa
                    $sourceId=[int]$request.arguments.origen_id
                    if (-not $companies.Contains($company) -or $sourceId -le 0) { throw 'Comprobante no válido.' }
                    $rows=@(Read-Tango $db $company "SELECT h.T_COMP AS tipo,h.N_COMP AS numero,t.PATH_PDF AS pdf_root FROM dbo.GVA12 h LEFT JOIN dbo.GVA43 t ON t.TALONARIO=h.TALONARIO WHERE h.ID_GVA12=$sourceId")
                    if ($rows.Count -ne 1) { throw 'Comprobante no encontrado.' }
                    $pdf=Find-Pdf $rows[0]
                    if (-not $pdf) { throw 'No hay un PDF accesible para este comprobante.' }
                    $outputPdf = Join-Path $responses ($request.id+'.pdf')
                    [IO.File]::Copy($pdf,$outputPdf,$true)
                    # Copy preserves the historic PDF timestamp. Queue TTL starts now.
                    [IO.File]::SetLastWriteTimeUtc($outputPdf,[datetime]::UtcNow)
                    $packet=@{version=1;id=$request.id;ok=$true}
                } else { throw 'Operación no permitida.' }
            } catch {
                $packet=@{version=1;id=$job.BaseName;ok=$false;error='No se pudo completar la consulta. Revisá que la interfaz Access esté abierta y conectada a Tango.'}
                # Only types are logged: no SQL, connection strings, credentials or customer data.
                Add-Content -LiteralPath (Join-Path $BridgeRoot 'worker.log') -Value ([datetime]::UtcNow.ToString('s')+' '+$_.Exception.GetType().Name+' line '+$_.InvocationInfo.ScriptLineNumber+' '+$_.ScriptStackTrace)
            } finally {
                if ($db) {[void][Runtime.InteropServices.Marshal]::ReleaseComObject($db)}
                if ($app) {[void][Runtime.InteropServices.Marshal]::ReleaseComObject($app)}
                if ($packet) {Write-AtomicJson (Join-Path $responses ($job.BaseName+'.json')) $packet}
                Remove-Item -LiteralPath $job.FullName -Force -ErrorAction SilentlyContinue
            }
        }
        # Cleanup only individual expired responses within this connector's directory.
        Get-ChildItem -LiteralPath $responses -File | Where-Object {$_.LastWriteTimeUtc -lt [datetime]::UtcNow.AddMinutes(-20)} | ForEach-Object {Remove-Item -LiteralPath $_.FullName -Force}
        if (-not $Once) {Start-Sleep -Milliseconds 350}
    } while (-not $Once)
} finally {
    Remove-Item -LiteralPath (Join-Path $BridgeRoot 'heartbeat.json') -Force -ErrorAction SilentlyContinue
    $workerLock.Dispose()
}
