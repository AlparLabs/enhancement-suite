{
    'name': 'Account Follow-up Residual Column',
    'version': '19.0.0.0.1',
    'category': 'Accounting/Accounting',
    'summary': 'Adds residual amount column to Follow-up Report and filters paid invoices',
    'description': """
        This module extends the Follow-up Report with two improvements:

        1. Filters paid/reversed invoices from the report (both the letter/PDF and the
           UI Follow-Up Report). This prevents invoices that are fully paid from appearing
           as outstanding, which can occur due to data integrity issues where a move line
           remains unreconciled at the database level despite the invoice being paid.

        2. Adds a "Residual (Company Currency)" column to the follow-up letter/PDF showing
           the outstanding balance in the company currency. This is especially useful in
           multi-currency environments where the existing "Total Due" column displays amounts
           in the invoice currency.
    """,
    'author': 'AlparData',
    'website': 'https://www.alpardata.com.ar',
    'depends': ['account_followup'],
    'data': [],
    'installable': True,
    'auto_install': False,
    'license': 'OPL-1',
}
