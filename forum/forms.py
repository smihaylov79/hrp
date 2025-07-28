from django import forms
from .models import *


class CategoryForm(forms.ModelForm):
    class Meta:
        model = Category
        fields = ["name", "description"]


class ThreadForm(forms.ModelForm):
    class Meta:
        model = Thread
        fields = ["title"]


class PostForm(forms.ModelForm):
    class Meta:
        model = Post
        fields = ["content"]
        widgets = {
            "content": forms.Textarea(attrs={"class": "form-control", "placeholder": "Напиши отговор..."}),
        }
        labels = {
            'content': 'Съдържание'
        }


class ThreadRequestForm(forms.ModelForm):
    class Meta:
        model = ThreadRequest
        fields = ["title", "description"]
        labels = {
            'title': 'Заглавие',
            'description': 'Описание'
        }


class UpdateThreadRequestForm(forms.ModelForm):
    class Meta:
        model = ThreadRequest
        fields = "__all__"
        widgets = {
            'status': forms.RadioSelect,
        }