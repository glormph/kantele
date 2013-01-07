from django.shortcuts import render, HttpResponse

def home(request):
    return render(request, 'kantele/index.html')
