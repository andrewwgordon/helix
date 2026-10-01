"""Mixin for service-backed ``SimpleFormView`` forms (spec §15.3).

Provides two small behaviours shared by the create/revise/structure forms:

* re-render the form template (with ``edit_fieldsets``) after a service error,
* attach a domain error to a specific form field when the exception names one.
"""

from app.services.exceptions import PlmError


class ServiceFormMixin:
    """Shared helpers for ``SimpleFormView`` subclasses that call services."""

    def render_service_form(self, form):
        """Re-render the standard edit template for ``form``."""
        widgets = self._get_edit_widget(form=form)
        return self.render_template(
            self.form_template,
            title=self.form_title,
            widgets=widgets,
            appbuilder=self.appbuilder,
        )

    @staticmethod
    def attach_field_error(form, exc: PlmError) -> bool:
        """Attach ``exc`` to its named field. Returns True when attached."""
        field = getattr(exc, "field", None)
        if field and hasattr(form, field):
            getattr(form, field).errors.append(str(exc))
            return True
        return False
