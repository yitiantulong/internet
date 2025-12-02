(function () {
    function updateBioCounter(textarea, counter) {
        if (!textarea || !counter) {
            return;
        }
        var length = textarea.value ? textarea.value.length : 0;
        counter.textContent = length + " / 8000";
    }

    function toggleEditSection(show) {
        var editSection = document.getElementById("profile-edit-section");
        var editToggle = document.getElementById("profile-edit-toggle");
        if (!editSection || !editToggle) {
            return;
        }
        if (show) {
            editSection.classList.remove("d-none");
            editToggle.classList.add("d-none");
            var firstInput = editSection.querySelector("input, textarea");
            if (firstInput) {
                setTimeout(function () {
                    firstInput.focus();
                }, 100);
            }
        } else {
            editSection.classList.add("d-none");
            editToggle.classList.remove("d-none");
        }
    }

    function initializeProfileEditor() {
        var form = document.querySelector('[data-role="profile-form"]');
        if (!form) {
            return;
        }
        var bioInput = form.querySelector("#profile-bio");
        var counter = form.querySelector('[data-role="bio-counter"]');
        var editToggle = document.getElementById("profile-edit-toggle");
        var cancelButtons = document.querySelectorAll("#profile-edit-cancel, #profile-edit-cancel-form");

        if (bioInput && counter) {
            updateBioCounter(bioInput, counter);
            bioInput.addEventListener("input", function () {
                updateBioCounter(bioInput, counter);
            });
        }

        if (editToggle) {
            editToggle.addEventListener("click", function () {
                toggleEditSection(true);
            });
        }

        cancelButtons.forEach(function (button) {
            button.addEventListener("click", function () {
                toggleEditSection(false);
            });
        });

        form.addEventListener("submit", function () {
            toggleEditSection(false);
        });
    }

    document.addEventListener("DOMContentLoaded", initializeProfileEditor);
})();

