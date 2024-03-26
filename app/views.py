from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from app.forms import SearchForm
from app.models import Societe
from guard.models import CustomUser
from utils.script import get_choix, check_base, write_log, get_cell_data


def get_data_from_form(form):
    data = None
    name = None
    debut = None
    fin = None
    if form.is_valid():
        name = form.cleaned_data['societe']
        debut = form.cleaned_data.get('debut').strftime("%m/%d/%Y")
        fin = form.cleaned_data.get('fin').strftime("%m/%d/%Y")
        filter_values = form.cleaned_data['filtre']

        if filter_values not in ['', None] and len(filter_values) == 0:
            data = get_choix(societe=name, where=True)
            if data is not None:
                data = [str(value) for value in data]
                data = ','.join(data)
        else:
            filter_values = filter(lambda x: x != '', filter_values)
            data = [str(value) for value in filter_values]
            data = ','.join(data)
    return name, debut, fin, data


@login_required
# Create your views here.
def get(request):
    datas = []
    name = "Home"
    if request.method == 'GET':
        form = SearchForm(request.GET)

    else:
        form = SearchForm(request.POST)
        name, debut, fin, data = get_data_from_form(form)
        if data:
            societe = Societe.objects.get(name__exact=name, active__exact=True)
            if societe:
                from utils.script import get_all_data
                check = check_base(server=societe.connexion.server, name=societe.value, value=societe.base,
                                   username=societe.connexion.login, password=societe.connexion.password)
                if check is not None:
                    gets = get_all_data(
                        categories=societe.connexion.types,
                        conn=check,
                        debut=debut,
                        fin=fin,
                        filtre=data
                    )
                    datas = gets[1]
                    check.close()
                    if not gets[0]:
                        messages.warning(request, "Erreur sur le choix de serveur ou la base n'a pas de donnée!")
                        write_log("Erreur sur le choix de serveur ou la base n'a pas de donnée!")
                else:
                    messages.error(request,
                                   f"Le serveur \"{societe.connexion.server}\" de la base \" {societe.value} \" n'est pas accessible !")
            else:
                messages.error(request, "Base Introuvable !")
        else:
            messages.warning(request, "Formulaires n'est pas valide !")
    # print(form)
    context = {
        'datas': datas,
        'form': form,
        'name': name,
        'societes': Societe.objects.all().order_by('name'),
        'path': request.path,
        'users_gets': CustomUser.objects.all(),
    }
    return render(request, 'app/get.html', context)


@login_required
def admin_view(request):
    context = {
        'path': request.path,
        'datas': Societe.objects.filter(active__exact=True).order_by('name'),
        'users_gets': CustomUser.objects.all().order_by('-date_joined'),
    }
    return render(request, "app/change.html", context)


@csrf_exempt
@login_required
def update_user_field(request):
    if request.method == 'POST':
        user_id = request.POST.get('user_id')
        field = request.POST.get('field')
        checked = request.POST.get('checked')
        # print(field, " : ", checked)
        if checked == 'true':
            checked = True
        else:
            checked = False
        user = get_object_or_404(CustomUser, id=user_id)
        setattr(user, field, checked)
        user.save()
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'})


@csrf_exempt
@login_required
def update_societe_field(request):
    if request.method == 'POST':
        societe_id = request.POST.get('societe_id')
        field = request.POST.get('field')
        checked = request.POST.get('checked')
        # print(field, " : ", checked)
        if checked == 'true':
            checked = True
        else:
            checked = False
        societe = get_object_or_404(Societe, uid=societe_id)
        setattr(societe, field, checked)
        societe.save()
        return JsonResponse({'status': 'success'})

    return JsonResponse({'status': 'error'})


@login_required
def delete_user(request, id):
    user = get_object_or_404(CustomUser, id=id)
    user.delete()
    messages.success(request, "Utilisateur Supprimer")
    return redirect('home:admin-views')


@login_required
def delete_societe(request, uid):
    societe = get_object_or_404(Societe, uid=uid)
    societe.active = False
    societe.save()
    messages.success(request, "Société Supprimer")
    return redirect('home:admin-views')


@login_required
def show_modal(request):
    return JsonResponse({'success': True, 'data': []})


@login_required
def cell_details_view(request):
    header = ['N° Piece', 'Date', 'Reference', 'Designation', 'Quantité', 'Prix Unitaire', 'Prix Total']
    try:
        column_index = request.POST.get('columnIndex', None)
        row_index = request.POST.get('rowIndex', None)
        cell_content = request.POST.get('cellContent', None)
        first_cell_content = request.POST.get('firstCellContent', None)
        value = request.POST.get('societe', None)
        debut = request.POST.get('debut', None)
        fin = request.POST.get('fin', None)
        filtre = request.POST.getlist('filtre[]', None)
        if filtre == [] or filtre == [''] or filtre is None:
            data = get_choix(societe=value, where=True)
            if data is not None:
                data = [str(value) for value in data]
                data = ','.join(data)
        else:
            filtre = filter(lambda x: x != '', filtre)
            data = [str(value) for value in filtre]
            data = ','.join(data)
        datas = []
        societe = Societe.objects.filter(name__exact=value, active__exact=True).first()
        check = check_base(server=societe.connexion.server, name=societe.value, value=societe.base,
                           username=societe.connexion.login, password=societe.connexion.password)
        if check is not None and societe:
            datas = get_cell_data(
                index=first_cell_content,
                conn=check,
                debut=debut,
                fin=fin,
                column=column_index,
                filtre=data
            )
            check.close()

        response_data = {
            'data': datas,
            'cell_content': cell_content,
            'header': header,
        }
        # print(f"Data : {datas}")

    except Exception as e:
        write_log(f"Erreur de {str(e)}")
        # print(f"Erreur : {str(e)}")
        response_data = {
            'data': [],
            'cell_content': 0,
            'header': header,  # You can customize this header as needed
            'error': str(e)  # Add the error message to the response for debugging
        }
    # print("Donnee envoyer")
    return JsonResponse(response_data)
