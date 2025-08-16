from django import forms
import datetime

class InsurerEmailForm(forms.Form):
    police_number = forms.CharField(label="Policy number", max_length=100, initial = "900025237612")
    insured_name = forms.CharField(label="Person to Insure", max_length=200, initial="Chris Judkins")
    birth_date = forms.DateField(
        label="Birth date",
        widget=forms.DateInput(attrs={"type": "date"}),
        initial = datetime.date(1999, 11, 24))
    
    start_date = forms.DateField(
    label="Start date",
    widget=forms.DateInput(attrs={"type": "date"})
    )
    end_date = forms.DateField(
    label="End date",
    widget=forms.DateInput(attrs={"type": "date"})
    )
    sender_name = forms.CharField(label="Sender name", max_length=200, initial="Chris Judkins")



                