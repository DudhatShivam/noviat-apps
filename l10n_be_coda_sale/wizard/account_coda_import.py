# -*- coding: utf-8 -*-
# Copyright 2009-2018 Noviat.
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl).

from odoo import models


class AccountCodaImport(models.TransientModel):
    _inherit = 'account.coda.import'

    def _get_sale_order(self, st_line, cba, transaction, reconcile_note):
        """
        check matching Sales Order number in free form communication
        """
        free_comm = repl_special(transaction['communication'].strip())
        select = \
            "SELECT id FROM (SELECT id, name, '%s'::text AS free_comm, " \
            "regexp_replace(name, '[0]{3,10}', '0%%0') AS name_match " \
            "FROM sale_order WHERE state not in ('cancel', 'done') " \
            "AND company_id = %s) sq " \
            "WHERE free_comm ILIKE '%%'||name_match||'%%'" \
            % (free_comm, cba.company_id.id)
        self._cr.execute(select)
        res = self._cr.fetchall()
        return reconcile_note, res

    def _match_sale_order(self, st_line, cba, transaction, reconcile_note):

        match = {}

        if transaction['communication'] and cba.find_so_number \
                and transaction['amount'] > 0:
            reconcile_note, so_res = self._get_sale_order(
                st_line, cba, transaction, reconcile_note)
            if so_res and len(so_res) == 1:
                so_id = so_res[0][0]
                match['sale_order_id'] = so_id
                sale_order = self.env['sale.order'].browse(so_id)
                partner = sale_order.partner_id.commercial_partner_id
                transaction['partner_id'] = partner.id
                inv_ids = [x.id for x in sale_order.invoice_ids]
                if inv_ids:
                    amount_fmt = '%.2f'
                    if transaction['amount'] > 0:
                        amount_rounded = \
                            amount_fmt % round(transaction['amount'], 2)
                    else:
                        amount_rounded = amount_fmt \
                            % round(-transaction['amount'], 2)
                    self._cr.execute(
                        "SELECT id FROM account_invoice "
                        "WHERE state = 'open' AND amount_total = %s "
                        "AND id in %s",
                        (amount_rounded, tuple(inv_ids)))
                    res = self._cr.fetchall()
                    if res:
                        inv_ids = [x[0] for x in res]
                        if len(inv_ids) == 1:
                            invoice = self.env['account.invoice'].browse(
                                inv_ids[0])
                            imls = self.env['account.move.line'].search(
                                [('move_id', '=', invoice.move_id.id),
                                 ('reconcile_id', '=', False),
                                 ('account_id', '=', invoice.account_id.id)])
                            if imls:
                                transaction['reconcile'] = imls[0].id

        return reconcile_note, match


def repl_special(s):
    s = s.replace("\'", "\'" + "'")
    return s
