from aiogram.fsm.state import State, StatesGroup


class SimulateFlow(StatesGroup):
    mode_select = State()
    express_revenue = State()
    express_accountants = State()
    express_salary = State()
    precise_clients = State()
    precise_contacts = State()
    precise_contact_name = State()
    precise_contact_email = State()
    precise_contact_phone = State()
    precise_contact_company = State()
    precise_contact_website = State()
    precise_margin = State()
    precise_standardization = State()
    precise_automation = State()
    precise_advisory = State()
    precise_growth = State()
    precise_mna = State()
    precise_wait_excel = State()


class MeetingBookingFlow(StatesGroup):
    waiting_email = State()
    waiting_date = State()
    waiting_custom_time = State()


class ValuationFlow(StatesGroup):
    mode_select = State()
    express_revenue = State()
    express_share = State()
    express_profitability = State()
    express_continue = State()
    precise_clients_total = State()
    precise_clients_key = State()
    precise_top5_share = State()
    precise_headcount = State()
    precise_automation_level = State()
    precise_automation_tools = State()
    precise_post_result = State()
