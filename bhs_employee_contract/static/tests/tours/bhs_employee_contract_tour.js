import { registry } from "@web/core/registry";
import { stepUtils } from "@web_tour/tour_utils";

/**
 * Contract menus of bhs_employee_contract opened by each role (data seeded in tests/test_functional_ui.py).
 * Rows are matched by employee name.
 */
const row = (name) => `.o_list_view .o_data_row:contains("${name}")`;
const noRow = (name) => `.o_list_view:not(:has(.o_data_row:contains("${name}")))`;

registry.category("web_tour.tours").add("bhs_ecm_hr_manager_contracts_tour", {
    steps: () => [
        {
            content: "Running contracts of active employees are listed",
            trigger: row("ECM Tour Sub Bob"),
            // First step after the page load: slower under coverage / right after -u
            timeout: 30000,
        },
        { content: "Other running contract listed", trigger: row("ECM Tour Other Dan") },
        { content: "Trainee contracts are not listed", trigger: noRow("ECM Tour Trainee Eve") },
        { content: "Expired contract not listed by default", trigger: noRow("ECM Tour Expired Fay") },
        {
            content: "Open the search options",
            trigger: ".o_searchview_dropdown_toggler",
            run: "click",
        },
        {
            content: "Add the Expired Contracts filter",
            trigger: '.o_filter_menu .o-dropdown-item:contains("Expired Contracts")',
            run: "click",
        },
        {
            content: "The expired (archived) contract is listed",
            trigger: row("ECM Tour Expired Fay"),
        },
    ],
});

const openByMenu = (xmlid) => [
    stepUtils.showAppsMenuItem(),
    {
        content: "Open the Employees app",
        trigger: '.o_app[data-menu-xmlid="hr.menu_hr_root"]',
        timeout: 30000,
        run: "click",
    },
    {
        content: "Open the Contracts menu of the module",
        trigger: '.o_main_navbar [data-menu-xmlid="bhs_employee_contract.hr_menu_contracts_root"]',
        // the navbar sections render after the app loads: slower under coverage
        timeout: 30000,
        run: "click",
    },
    {
        content: `Open ${xmlid}`,
        trigger: `.o-dropdown--menu [data-menu-xmlid="${xmlid}"]`,
        run: "click",
    },
];

registry.category("web_tour.tours").add("bhs_ecm_ml_contracts_tour", {
    steps: () => [
        ...openByMenu("bhs_employee_contract.hr_menu_contract"),
        {
            content: "Own subtree contract listed",
            trigger: row("ECM Tour Sub Bob"),
            timeout: 30000,
        },
        { content: "Contract outside the subtree hidden", trigger: noRow("ECM Tour Other Dan") },
        { content: "Trainee of the subtree hidden (employee contracts menu)", trigger: noRow("ECM Tour Trainee Carl") },
    ],
});

registry.category("web_tour.tours").add("bhs_ecm_trainee_contracts_tour", {
    steps: () => [
        ...openByMenu("bhs_employee_contract.hr_menu_trainee_contract"),
        {
            content: "Trainee contract listed",
            trigger: row("ECM Tour Trainee Eve"),
            timeout: 30000,
        },
        { content: "Other trainee listed", trigger: row("ECM Tour Trainee Carl") },
        { content: "Employee contracts hidden", trigger: noRow("ECM Tour Other Dan") },
    ],
});
