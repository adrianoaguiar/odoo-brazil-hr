# -*- coding: utf-8 -*-
# Copyright (C) 2019  Luiz Felipe do Divino - ABGF
# License AGPL-3 - See http://www.gnu.org/licenses/agpl-3.0.html

from openerp import api, models, fields

TIPO_ACORDOS = [
    ('A', 'Acordo Coletivo de Trabalho'),
    ('B', 'Legislação Federal, Estadual, Municipal ou Distrital'),
    ('C', 'Convenção Coletiva de Trabalho'),
    ('D', 'Setença Normativa - Dissídio'),
    ('E', 'Conversão de Licença Saúde em Acidente de Trabalho'),
    ('F', 'Outras verbas de natureza salarial ou não salarial devidas após o desligamento'),
]


class L10nBrHrAcordoColetivo(models.Model):
    _name = 'l10n.br.hr.acordo.coletivo'

    name = fields.Char(
        string='name',
        compute='_compute_name'
    )
    data_assinatura_acordo = fields.Date(
        string='Data Assinatura Acordo',
    )
    tipo_acordo = fields.Selection(
        string='Tipo do Acordo',
        selection=TIPO_ACORDOS,
    )
    competencia_pagamento = fields.Many2one(
        string='Competência de Pagamento',
        comodel_name='account.period',
        help='Competência em que será preciso pagar os '
             'valores reajustados e retroativos',
    )
    data_efetivacao = fields.Date(
        string='Data da Efetivação Retroativa',
    )
    descricao = fields.Char(
        string=u'Descrição',
    )
    remuneracao_relativa_sucessao = fields.Selection(
        string='Remuneração relativa a sucessão',
        selection=[
            ('S', 'Sim'),
            ('N', u'Não'),
        ],
        help='Indicar se a remuneração é relativa a verbas de natureza salarial '
             'ou não salarial devidas pela empresa sucessora a empregados '
             'desligados ainda na sucedida',
    )
    valor_reajuste_salarial = fields.Float(
        string='Valor Reajuste(%)',
    )

    rubrica_ids = fields.One2many(
        string=u'Rúbricas',
        comodel_name='l10n.br.hr.acordo.coletivo.rubricas',
        inverse_name='acordo_coletivo_id',
    )

    periodo_ids = fields.One2many(
        string='Periodos',
        comodel_name='account.period',
        inverse_name='acordo_coletivo_id',
    )

    diferenca_periodo_ids = fields.One2many(
        string=u'Diferenças nos períodos',
        comodel_name='hr.contract.salary.rule',
        inverse_name='acordo_coletivo_id'
    )

    @api.multi
    def _compute_name(self):
        for record in self:
            record.name = 'Acordo Coletivo - {}'.format(
                record.competencia_pagamento.code or '--/----')

    @api.multi
    def _get_periodos_retroativos(self):
        for record in self:
            periodos = self.env['account.period'].search(
                [
                    ('date_start', '>=', record.data_efetivacao),
                    ('date_stop', '<', record.competencia_pagamento.date_stop),
                    ('special', '=', False),
                ]
            )

            record.periodo_ids = [(6, 0, periodos.ids)]

    @api.multi
    def _get_dicionario_rubricas(self):
        rubricas = {}
        for rubrica in self.rubrica_ids:
            rubricas[rubrica.rubrica_holerite_id.id] = \
                rubrica.rubrica_diferenca_id.id

        return rubricas

    @api.multi
    def _get_diferencas_retroativas(self):
        for record in self:

            if not record.periodo_ids:
                record._get_periodos_retroativos()

            record.diferenca_periodo_ids.unlink()

            contract_ids = self.env['hr.contract'].search(
                [('date_end', '=', False)])

            rubricas = record._get_dicionario_rubricas()

            for contrato in contract_ids:
                for periodo in record.periodo_ids:
                    payslip_ids = self.env['hr.payslip'].search(
                        [('date_from', '>=', periodo.date_start),
                         ('date_from', '<=', periodo.date_stop),
                         ('tipo_de_folha', 'in', ['normal', 'ferias']),
                         ('contract_id', '=', contrato.id)]
                    )

                    for payslip in payslip_ids:
                        for line in payslip.line_ids:
                            if rubricas.get(line.salary_rule_id.id):
                                record._gerar_linha_acordo_coletivo(
                                    contrato, line, periodo,
                                    record.competencia_pagamento,
                                    rubricas[line.salary_rule_id.id]
                                )

    def _gerar_linha_acordo_coletivo(
            self, contrato, line, periodo, competencia_pagamento, rubrica_id):
        valor_bruto = line.total
        porcentagem = 1 + (self.valor_reajuste_salarial / 100)
        valor_diferenca = (valor_bruto * porcentagem) - valor_bruto
        vals = {
            'contract_id': contrato.id,
            'rule_id': rubrica_id,
            'tipo_holerite': 'normal',
            'date_start': competencia_pagamento.date_start,
            'date_stop': competencia_pagamento.date_stop,
            'ref': '{}-{}'.format(periodo.code[3:], periodo.code[:2]),
            'specific_quantity': 1,
            'specific_percentual': 100,
            'specific_amount': valor_diferenca,
            'acordo_coletivo_id': self.id,
        }

        self.env['hr.contract.salary.rule'].create(vals)

    @api.multi
    def buscar_periodos_retroativos(self):
        for record in self:
            record._get_periodos_retroativos()

    @api.multi
    def gerar_diferencas_retroativos(self):
        for record in self:
            record._get_diferencas_retroativas()


class L10nBrHrAcordoColetivoRubrias(models.Model):
    _name = 'l10n.br.hr.acordo.coletivo.rubricas'

    rubrica_holerite_id = fields.Many2one(
        string=u'Rúbrica do Holerite',
        comodel_name='hr.salary.rule',
    )
    rubrica_diferenca_id = fields.Many2one(
        string=u'Rúbrica da Diferença',
        comodel_name='hr.salary.rule',
    )
    acordo_coletivo_id = fields.Many2one(
        string='Acordo Coletivo',
        comodel_name='l10n.br.hr.acordo.coletivo',
    )
