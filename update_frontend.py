import sys

with open('frontend/src/pages/DetalleAcopio.tsx', 'r', encoding='utf-8') as f:
    content = f.read()

content = content.replace(
    '''                                            {imp.es_excedente && (
                                                <span className="consumos-badge-excedente">⚠ Excedente</span>
                                            )}''',
    '''                                            {imp.es_excedente && imp.excedente_tipo !== 'ITEM' && imp.excedente_tipo !== 'COMPOSICION' && (
                                                <span className="consumos-badge-excedente" title={imp.excedente_motivo || ''}>⚠ {imp.excedente_tipo === 'ACOPIO' ? 'Excedente acopio' : 'Excedente'}</span>
                                            )}
                                            {imp.excedente_tipo === 'ITEM' && (
                                                <span className="consumos-badge-excedente" title={imp.excedente_motivo || ''} style={{ backgroundColor: '#fff3cd', color: '#856404' }}>⚠ Excedente ítem</span>
                                            )}
                                            {imp.excedente_tipo === 'COMPOSICION' && (
                                                <span className="consumos-badge-excedente" title={imp.excedente_motivo || ''} style={{ backgroundColor: '#fff3cd', color: '#856404' }}>⚠ Revisar composición</span>
                                            )}'''
)

content = content.replace(
    '''                                        <td>{imp.es_excedente ? '⚠️ Sí' : 'No'}</td>''',
    '''                                        <td title={imp.excedente_motivo || ''}>
                                            {imp.excedente_tipo === 'ACOPIO' ? '⚠️ Sí (Acopio)' :
                                             imp.excedente_tipo === 'ITEM' ? '⚠️ Sí (Ítem)' :
                                             imp.excedente_tipo === 'COMPOSICION' ? '⚠️ Composición' :
                                             imp.es_excedente ? '⚠️ Sí' : 'No'}
                                        </td>'''
)

with open('frontend/src/pages/DetalleAcopio.tsx', 'w', encoding='utf-8') as f:
    f.write(content)
