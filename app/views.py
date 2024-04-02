import decimal
import json
from datetime import datetime
from decimal import Decimal

from django.contrib import messages
from django.contrib.auth.decorators import login_required
from django.http import JsonResponse
from django.shortcuts import render, get_object_or_404, redirect
from django.views.decorators.csrf import csrf_exempt

from app.forms import SearchForm
from app.models import Societe
from guard.models import CustomUser
from utils.script import get_choix, check_base, write_log, get_cell_data, are_valid_uuids, get_data


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
        print(request.POST)
        form = SearchForm(request.POST)
        try:
            if form.is_valid():
                societe = form.cleaned_data['societe']
                begin = form.cleaned_data.get('debut').strftime("%d/%m/%Y")
                end = form.cleaned_data.get('fin').strftime("%d/%m/%Y")

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
                            if conn is not None:
                                data = get_choix(conn=conn)
                                filters = data
                                conn.close()
                        except Exception as e:
                            write_log(str(e))
                            pass
                    uid = item.pk
            else:
                print(f"Formulaire est invalide : {str(form.errors)}")
        except Exception as e:
            print(f"Erreur {str(e)}")
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
    print(request.POST)
    uid = are_valid_uuids(request.POST.get('uid'))
    begin = request.POST.get('begin')
    end = request.POST.get('end')
    filters = request.POST.getlist('filters')
    if None not in (begin, end, uid) and filters != '':
        societe = Societe.objects.get(uid__exact=uid)
        check = check_base(server=societe.connexion.server, name=societe.value, value=societe.base,
                           username=societe.connexion.login, password=societe.connexion.password)
        filter_values = ','.join(filters)
        if check is not None:
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

            gets = get_data(sql=sql, columns=["CATEGORY", "INTITULE"], conn=check)
            print(begin, end)
            if gets is not None and begin is not None and end is not None:
                begin = datetime.strptime(begin, "%d/%m/%Y").strftime("%Y-%m-%d")
                end = datetime.strptime(end, "%d/%m/%Y").strftime("%Y-%m-%d")
                lists = {
                    'STK_INTIALE': f"DL_MvtStock IN (1,3) and DL_DateBL<='{begin}'",
                    'EN_RETOUR': f"do_domaine IN (0) and Dl_QTE < 0 and DL_DateBL between '{begin}' and '{end}'",
                    'EN_RECEP': f"do_domaine IN (1) and DL_DateBL between '{begin}' and '{end}'",
                    'EN_PROD': f"do_type IN (40) and DL_DateBL between '{begin}' and '{end}'",
                    'EN_ASSEMB': None,
                    'EN_TRANS': f"do_type IN (23) and dl_mvtstock=1 and DL_DateBL between '{begin}' and '{end}'",
                    'EN_MVM': f"do_type IN (20) and DO_PIECE not like'i00%' and DL_DateBL between '{begin}' and '{end}'",
                    'EN_INV': f"do_type IN (20) and DO_PIECE like'i00%' and DL_DateBL between '{begin}' and '{end}'",
                    'TOTAL_EN': None,
                    'SO_VENTE': f"do_domaine IN (0) and Dl_QTE > 0 and DL_DateBL between '{begin}' and '{end}'",
                    'SO_CONSO': f"do_type IN (41) and DL_DateBL between '{begin}' and '{end}'",
                    'SO_DESAS': None,
                    'SO_TRANS': f"do_type IN (23) and dl_mvtstock=3 and DL_DateBL between '{begin}' and '{end}'",
                    'SO_MVM': f"do_type IN (21) and DO_PIECE not like'i00%' and DL_DateBL between '{begin}' and '{end}'",
                    'SO_INV': f"do_type IN (21) and DO_PIECE like'i00%' and DL_DateBL between '{begin}' and '{end}'",
                    'TOTAL_SO': None,
                    'STK_FINAL_CAL': None,
                    'STK_FINAL_SYS': f"DL_MvtStock IN (1,3) and DL_DateBL<='{end}'"
                }
                wheres = []
                for key, value in lists.items():
                    if value is not None:
                        query = query.replace('{where}', value).replace('{in}', filter_values)
                        # print(f"=================================================")
                        # print("QUERY: ", query)
                        # print(f"=================================================")
                        val = get_data(sql=query, columns=["FAMILLE", "VALUE"], conn=check)
                        # print(f"=================================================")
                        # print("VAL: ", val)
                        # print(f"=================================================")
                        if val is not None:
                            val = {key: val.to_dict(orient='records')}
                        else:
                            val = {key: []}
                    else:
                        val = {key: []}
                    wheres.append(val)
                print(f"=================================================")
                print("WHERES: ", wheres[0])
                print(f"=================================================")
                for index, row in gets.iterrows():
                    lines = {"CATEGORY": row['CATEGORY'], "INTITULE": row['INTITULE']}
                    for key, value in lists.items():
                        if key in wheres:
                            print(f"=================================================")
                            print(f"{key}: {wheres[key]}")
                            print(f"=================================================")
                        # else:
                        #     print(f"{key} N'existe pas !")
                        # find_list = wheres[key]

                        # if find_list:
                        #     category_value = next((x['VALUE'] for x in find_list if x.get('FAMILLE') == row['CATEGORY']), 0)
                        # else:
                        #     category_value = 0
                        # lines[item['key']] = category_value
                    # datas.append(lines)
            check.close()
        else:
            messages.warning(request, f"Erreur de connexion a la base {societe.name} !")
            return redirect('app:get')
    context = {
        "data": datas
    }
    # print(f"=================================================")
    # print(f"{context}")  # Corrected line
    # print("=======================================================")
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
        begin = request.POST.get('begin', None)
        end = request.POST.get('end', None)
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
                debut=begin,
                fin=end,
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
