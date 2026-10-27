// The top bar's link menu (LINK_MENU in widgets/robot_link_ui.py), a native
// <details> opened by its status pill. A click anywhere outside it, or Esc,
// closes it, as a dropdown menu does; on Esc the pill gets the focus back.
(() => {
    var MENU_ID = "link-menu";

    function openMenu() {
        var menu = document.getElementById(MENU_ID);
        return menu && menu.open ? menu : null;
    }

    document.addEventListener("pointerdown", (event) => {
        var menu = openMenu();
        if (menu && !menu.contains(event.target)) {
            menu.open = false;
        }
    });

    document.addEventListener("keydown", (event) => {
        var menu = openMenu();
        if (menu && event.key === "Escape") {
            menu.open = false;
            menu.querySelector("summary").focus();
        }
    });

    // Opened, the address is ready to type into.
    document.addEventListener(
        "toggle",
        (event) => {
            var menu = event.target;
            if (menu.id === MENU_ID && menu.open) {
                var input = menu.querySelector("input");
                if (input) {
                    input.focus();
                    input.select();
                }
            }
        },
        true,
    );
})();
