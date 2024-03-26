from django import forms
from django.contrib.auth.forms import UserChangeForm

from app.models import Societe
from guard.models import CustomUser
from utils.script import get_choix


class SearchForm(forms.Form):
    debut = forms.DateField(
        label='Début',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    fin = forms.DateField(
        label='Fin',
        widget=forms.DateInput(attrs={'type': 'date', 'class': 'form-control'})
    )

    filtre = forms.MultipleChoiceField(
        label='Depot',
        widget=forms.SelectMultiple(
            attrs={
                'class': 'form-select form-select-sm w-100',
                'multiselect-search': 'true',
                'data-live-search': 'true',
                'multiple': 'multiple',
                'data-live-search-placeholder': 'Search',
                'tabindex': '-98'
            }
        ),
        required=False
    )

    def __init__(self, *args, **kwargs):
        super(SearchForm, self).__init__(*args, **kwargs)

        # Dynamically populate the choices for the 'societe' field
        societe_choices = []
        societe_choices.extend(
            (societe.name, societe.name) for societe in Societe.objects.filter(active__exact=True).order_by('name')
        )

        self.fields['societe'] = forms.ChoiceField(
            choices=societe_choices,
            label='Société',
            widget=forms.Select(attrs={'class': 'form-select'})
        )

        societe_name = self.data.get('societe')

        if societe_name:
            choices = get_choix(societe_name)
            if choices is None:
                choices = []
            self.fields['filtre'].choices = choices


class CustomUserChangeForm(UserChangeForm):
    class Meta(UserChangeForm.Meta):
        model = CustomUser
        fields = ('first_name', 'last_name', 'email')
        widgets = {
            'first_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'First Name'}),
            'last_name': forms.TextInput(attrs={'class': 'form-control', 'placeholder': 'Last Name'}),
            'email': forms.EmailInput(attrs={'class': 'form-control', 'placeholder': 'Email'}),
        }
