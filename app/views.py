import json

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from app.forms import SearchForm
from app.models import Societe
from guard.models import CustomUser
from utils.script import get_choix, check_base, write_log, get_cell_data, are_valid_uuids, get_all_filter, \
    get_sql, get_data


def get_data_from_form(societe, debut, fin, filter_values):
    datas = []
    check = check_base(server=societe.connexion.server, name=societe.value, value=societe.base,
                       username=societe.connexion.login, password=societe.connexion.password)
    filter_values = ','.join(filter_values)
    with open('data.json', 'r') as file:
        try:
            json_file = json.load(file)
            sql = json_file['FAMILLE']
            sql = sql.replace('{in}', str(filter_values))
            query = json_file['COLUMN']
        except Exception as e:
            write_log(e)
            sql = None
            query = None

        # print("=================================================")
        # print(sql)
        # print("=================================================")

        gets = get_data(sql=sql, columns=["CATEGORY", "INTITULE"], conn=check)
        where = {
            '1': f"DL_MvtStock IN (1,3) and DL_DateBL<='{debut}'",
            '2': f"do_domaine IN (0) and Dl_QTE < 0 and DL_DateBL between '{debut}' and '{fin}'",
            '3': f"do_domaine IN (1) and DL_DateBL between '{debut}' and '{fin}'",
            '4': f"do_type IN (40) and DL_DateBL between '{debut}' and '{fin}'",
            '5': None,
            '6': f"do_type IN (23) and dl_mvtstock=1 and DL_DateBL between '{debut}' and '{fin}'",
            '7': f"do_type IN (20) and DO_PIECE not like'i00%' and DL_DateBL between '{debut}' and '{fin}'",
            '8': f"do_type IN (20) and DO_PIECE like'i00%' and DL_DateBL between '{debut}' and '{fin}'",
            '9': None,
            '10': f"do_domaine IN (0) and Dl_QTE > 0 and DL_DateBL between '{debut}' and '{fin}'",
            '11': f"do_type IN (41) and DL_DateBL between '{debut}' and '{fin}'",
            '12': None,
            '13': f"do_type IN (23) and dl_mvtstock=3 and DL_DateBL between '{debut}' and '{fin}'",
            '14': f"do_type IN (21) and DO_PIECE not like'i00%' and DL_DateBL between '{debut}' and '{fin}'",
            '15': f"do_type IN (21) and DO_PIECE like'i00%' and DL_DateBL between '{debut}' and '{fin}'",
            '16': None,
            '17': None,
            '18': f"DL_MvtStock IN (1,3) and DL_DateBL<='{fin}'",
        }
        wheres = []
        for key, value in where.items():
            if value is not None:
                query = query.replace('{where}', value).replace('{in}', filter_values)
                val = get_data(sql=query, columns=["FAMILLE", "VALUE"], conn=check)
                if val is not None:
                    val = val.to_dict(orient='records')
                else:
                    val = []
            else:
                val = []
            wheres.append({'key': key, 'value': val})
        for index, row in gets.iterrows():
            lines = {'CATEGORY': row['CATEGORY'], 'INTITULE': row['INTITULE']}
            for i, j in where.items():
                find_list = wheres[int(i) - 1]['value']
                value = next((item['VALUE'] for item in find_list if item['FAMILLE'] == row['CATEGORY']), 0)
                lines[str(int(i) - 1)] = value
            datas.append(lines)

    return datas


@login_required
# Create your views here.
def get(request):
    datas = []
    uid = None
    societe = None
    begin = None
    end = None
    filters = []

    if request.method == 'GET':
        form = SearchForm(request.GET)
    else:
        form = SearchForm(request.POST)
        if form.is_valid():
            societe = form.cleaned_data['societe']
            begin = form.cleaned_data.get('debut').strftime("%m/%d/%Y")
            end = form.cleaned_data.get('fin').strftime("%m/%d/%Y")

            if societe is not None:
                item = Societe.objects.get(name__exact=societe)
                if item:
                    try:
                        conn = check_base(
                            server=item.connexion.server,
                            name=item.name,
                            value=item.value,
                            username=item.connexion.login,
                            password=item.connexion.password,
                        )
                        data = get_choix(conn=conn)
                        filters = data
                    except Exception as e:
                        write_log(str(e))
                        pass
                uid = item.pk
        else:
            print(f"Formulaire est invalide : {str(form.errors)}")
    context = {
        'datas': datas,
        'form': form,
        'uid': uid,
        'societe': societe,
        'begin': begin,
        'end': end,
        'filters': filters,
        'path': request.path,
        'users_gets': CustomUser.objects.all(),
    }
    return render(request, 'app/get.html', context)


@login_required
@csrf_exempt
def get_inventory_ajax(request):
    datas = []
    # data = json.loads(request.body)
    # print(f"POST : {data} ")
    uid = are_valid_uuids(request.POST.get('uid'))
    begin = request.POST.get('begin')
    end = request.POST.get('end')
    filters = request.POST.getlist('filters')
    if None not in (begin, end, uid) and filters != '':
        societe = Societe.objects.get(uid__exact=uid)
        datas = get_data_from_form(societe=societe, debut=begin, fin=end, filter_values=filters)
    context = {
        'datas': datas[0]
    }
    print(f"=================================================")
    print(f"{context}")  # Corrected line
    print("=======================================================")
    return JsonResponse(context, safe=False)


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
        # if filtre == [] or filtre == [''] or filtre is None:
        #     data = get_choix(societe=value, where=True)
        #     if data is not None:
        #         data = [str(value) for value in data]
        #         data = ','.join(data)
        # else:
        #     filtre = filter(lambda x: x != '', filtre)
        #     data = [str(value) for value in filtre]
        #     data = ','.join(data)
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
                filtre=filtre
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
