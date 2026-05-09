from django.contrib.auth.decorators import login_required
from django.shortcuts import redirect, render

from .selectors import module_selector_context


def landing_page(request):
    if request.user.is_authenticated:
        return redirect('module_selector')
    return render(request, 'public/home_page.html')


@login_required
def module_selector(request):
    return render(request, 'public/module_selector.html', module_selector_context(request.user))
