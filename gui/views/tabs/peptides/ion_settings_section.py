"""Ion matching settings section."""

import flet as ft

from api.calculations.spectra.ion_match import IonMatchParameters
from .base_section import BaseSection


class IonSettingsSection(BaseSection):
    """Ion matching parameters configuration."""

    def _build_content(self) -> ft.Control:
        # Ion type checkboxes
        self.ion_type_a_cb = ft.Checkbox(label="a", value=False)
        self.ion_type_b_cb = ft.Checkbox(label="b", value=True)
        self.ion_type_c_cb = ft.Checkbox(label="c", value=False)
        self.ion_type_x_cb = ft.Checkbox(label="x", value=False)
        self.ion_type_y_cb = ft.Checkbox(label="y", value=True)
        self.ion_type_z_cb = ft.Checkbox(label="z", value=False)

        # Loss checkboxes
        self.water_loss_cb = ft.Checkbox(label="Water loss (H₂O)", value=False)
        self.nh3_loss_cb = ft.Checkbox(label="Ammonia loss (NH₃)", value=False)

        # Threshold fields
        self.ion_ppm_threshold_field = ft.TextField(
            label="PPM Threshold", value="20",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.fragment_charges_field = ft.TextField(
            label="Fragment Charges", value="1,2",
            hint_text="e.g., 1,2,3", width=250
        )

        # Precursor charge settings for PPM calculation
        self.ignore_spectre_charges_cb = ft.Checkbox(
            label="Ignore spectre charges",
            value=True
        )
        self.min_precursor_charge_field = ft.TextField(
            label="Min precursor charge", value="1",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )
        self.max_precursor_charge_field = ft.TextField(
            label="Max precursor charge", value="4",
            width=150, keyboard_type=ft.KeyboardType.NUMBER
        )

        return ft.Column([
            ft.Text("Ion Matching Settings", size=18, weight=ft.FontWeight.BOLD),
            ft.Row([
                ft.Text("Ion Types:", weight=ft.FontWeight.W_500),
                self.ion_type_a_cb, self.ion_type_b_cb, self.ion_type_c_cb,
                self.ion_type_x_cb, self.ion_type_y_cb, self.ion_type_z_cb
            ], spacing=15),
            ft.Row([
                ft.Text("Losses:", weight=ft.FontWeight.W_500),
                self.water_loss_cb, self.nh3_loss_cb
            ], spacing=15),
            ft.Row([
                self.ion_ppm_threshold_field,
                self.fragment_charges_field
            ], spacing=10),
            ft.Row([
                self.ignore_spectre_charges_cb,
                self.min_precursor_charge_field,
                self.max_precursor_charge_field
            ], spacing=10)
        ], spacing=10)

    async def load_data(self):
        """Load ion settings from project."""
        try:
            ion_types_str = await self.project.get_setting('ion_types', 'b,y')
            ion_types = ion_types_str.split(',') if ion_types_str else []

            self.ion_type_a_cb.value = 'a' in ion_types
            self.ion_type_b_cb.value = 'b' in ion_types
            self.ion_type_c_cb.value = 'c' in ion_types
            self.ion_type_x_cb.value = 'x' in ion_types
            self.ion_type_y_cb.value = 'y' in ion_types
            self.ion_type_z_cb.value = 'z' in ion_types

            self.water_loss_cb.value = (await self.project.get_setting('water_loss', '0')) == '1'
            self.nh3_loss_cb.value = (await self.project.get_setting('nh3_loss', '0')) == '1'

            self.ion_ppm_threshold_field.value = await self.project.get_setting('ion_ppm_threshold', '20')
            self.fragment_charges_field.value = await self.project.get_setting('fragment_charges', '1,2')

            self.ignore_spectre_charges_cb.value = (
                await self.project.get_setting('ignore_spectre_charges', '1')
            ) == '1'
            self.min_precursor_charge_field.value = await self.project.get_setting(
                'min_precursor_charge', '1'
            )
            self.max_precursor_charge_field.value = await self.project.get_setting(
                'max_precursor_charge', '4'
            )

            self._sync_to_state()

        except Exception as ex:
            print(f"Error loading ion settings: {ex}")
            self.show_error(f"Error loading ion settings: {str(ex)}")

    async def save_settings(self):
        """Save ion settings to project."""
        selected_types = self._get_selected_ion_types()
        if not selected_types:
            raise ValueError("At least one ion type required")

        if float(self.ion_ppm_threshold_field.value) <= 0:
            raise ValueError("PPM threshold must be > 0")

        if not self.fragment_charges_field.value.strip():
            raise ValueError("Fragment charges required")

        await self.project.set_setting('ion_types', ','.join(selected_types))
        await self.project.set_setting('water_loss', '1' if self.water_loss_cb.value else '0')
        await self.project.set_setting('nh3_loss', '1' if self.nh3_loss_cb.value else '0')
        await self.project.set_setting('ion_ppm_threshold', self.ion_ppm_threshold_field.value)
        await self.project.set_setting('fragment_charges', self.fragment_charges_field.value)

        await self.project.set_setting(
            'ignore_spectre_charges', '1' if self.ignore_spectre_charges_cb.value else '0'
        )
        await self.project.set_setting(
            'min_precursor_charge', self.min_precursor_charge_field.value
        )
        await self.project.set_setting(
            'max_precursor_charge', self.max_precursor_charge_field.value
        )

        self._sync_to_state()

    def _get_selected_ion_types(self) -> list[str]:
        selected = []
        if self.ion_type_a_cb.value: selected.append('a')
        if self.ion_type_b_cb.value: selected.append('b')
        if self.ion_type_c_cb.value: selected.append('c')
        if self.ion_type_x_cb.value: selected.append('x')
        if self.ion_type_y_cb.value: selected.append('y')
        if self.ion_type_z_cb.value: selected.append('z')
        return selected

    def _sync_to_state(self):
        """Sync current UI values to shared state."""
        self.state.ion_types = self._get_selected_ion_types()
        self.state.water_loss = self.water_loss_cb.value
        self.state.nh3_loss = self.nh3_loss_cb.value
        self.state.ion_ppm_threshold = float(self.ion_ppm_threshold_field.value)
        self.state.fragment_charges = [
            int(c.strip())
            for c in self.fragment_charges_field.value.split(',')
            if c.strip()
        ]
        self.state.ignore_spectre_charges = self.ignore_spectre_charges_cb.value
        self.state.min_precursor_charge = int(self.min_precursor_charge_field.value or 1)
        self.state.max_precursor_charge = int(self.max_precursor_charge_field.value or 4)

    def get_ion_match_parameters(self) -> IonMatchParameters:
        """Create IonMatchParameters from current settings."""
        self._sync_to_state()
        return IonMatchParameters(
            ions=self.state.ion_types,
            tolerance=self.state.ion_ppm_threshold,
            mode='largest',
            water_loss=self.state.water_loss,
            ammonia_loss=self.state.nh3_loss,
            charges=self.state.fragment_charges
        )

    def get_charge_parameters(self) -> dict:
        """Return precursor charge parameters for coverage_worker."""
        self._sync_to_state()
        return {
            'ignore_spectre_charges': self.state.ignore_spectre_charges,
            'min_charge': self.state.min_precursor_charge,
            'max_charge': self.state.max_precursor_charge,
        }
