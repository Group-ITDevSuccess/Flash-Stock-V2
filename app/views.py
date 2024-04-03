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
from utils.script import get_choix, check_base, write_log, get_cell_data, are_valid_uuids, get_data, \
    find_value_in_wheres


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
        # print(request.POST)
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
    uid = are_valid_uuids(request.POST.get('uid'))
    begin = request.POST.get('begin')
    end = request.POST.get('end')
    filters = request.POST.getlist('filters')
    if None not in (begin, end, uid) and filters != '':
        societe = Societe.objects.get(uid__exact=uid)
        check = check_base(server=societe.connexion.server, name=societe.value, value=societe.base,
                           username=societe.connexion.login, password=societe.connexion.password)
        filter_values = ','.join(filters)
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
        if check is not None and query is not None and sql is not None:
            families = get_data(sql=sql, columns=["CATEGORY", "INTITULE"], conn=check)
            begin = datetime.strptime(begin, "%d/%m/%Y").strftime("%Y-%m-%d")
            end = datetime.strptime(end, "%d/%m/%Y").strftime("%Y-%m-%d")
            conditions = "and DE_No in({in})  group by FA_CodeFamille"
            lists = {
                'STK_INTIALE': f"{query} DL_MvtStock IN (1,3) and DL_DateBL<='{begin}' {conditions}",
                'EN_RETOUR': f"{query} do_domaine IN (0) and Dl_QTE < 0 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'EN_RECEP': f"{query} do_domaine IN (1) and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'EN_PROD': f"{query} do_type IN (40) and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'EN_ASSEMB': None,
                'EN_TRANS': f"{query} do_type IN (23) and dl_mvtstock=1 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'EN_MVM': f"{query} do_type IN (20) and DO_PIECE not like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'EN_INV': f"{query} do_type IN (20) and DO_PIECE like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'TOTAL_EN': None,
                'SO_VENTE': f"{query} do_domaine IN (0) and Dl_QTE > 0 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'SO_CONSO': f"{query} do_type IN (41) and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'SO_DESAS': None,
                'SO_TRANS': f"{query} do_type IN (23) and dl_mvtstock=3 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'SO_MVM': f"{query} do_type IN (21) and DO_PIECE not like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'SO_INV': f"{query} do_type IN (21) and DO_PIECE like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                'TOTAL_SO': None,
                'STK_FINAL_CAL': None,
                'STK_FINAL_SYS': f"{query} DL_MvtStock IN (1,3) and DL_DateBL<='{end}' {conditions}"
            }
            wheres = []
            if families is not None:
                for key, value in lists.items():
                    vals = {"NAME": key, "VALUES": []}
                    if value is not None:
                        details = get_data(
                            sql=value.replace('{in}', filter_values),
                            columns=["CATEGORY", "VALUES"],
                            conn=check
                        )
                        if details is not None:
                            vals['VALUES'] = details.to_dict(orient="records")
                    wheres.append(vals)

                check.close()

                for index, row in families.iterrows():
                    lines = {"CATEGORY": row["CATEGORY"], "INTITULE": row["INTITULE"]}
                    for key, value in lists.items():
                        lines[key] = find_value_in_wheres(wheres, key, row["CATEGORY"])
                    datas.append(lines)

        else:
            messages.warning(request, f"Erreur de connexion a la base {societe.name} !")
            return redirect('app:get')
    context = {
        "data": datas
    }
    # print(f"=================================================")
    # print(f"Data : {context}")  # Corrected line
    # print("=======================================================")
    return JsonResponse(context, safe=False)

@login_required
@csrf_exempt
def cell_details_view(request):
    datas = []
    try:
        info_table = json.loads(request.POST['info_table'])
        data_row = json.loads(request.POST['data_row'])[0]
        colonneCheck = json.loads(request.POST['data_cell'])
        begin = info_table.get('begin')
        end = info_table.get('end')

        societe = Societe.objects.filter(name__exact=info_table.get('societe'), active__exact=True).first()
        check = check_base(server=societe.connexion.server, name=societe.value, value=societe.base,
                           username=societe.connexion.login, password=societe.connexion.password)
        if check is not None and societe:
            with open('data.json', 'r') as file:
                try:
                    json_file = json.load(file)
                    query = json_file['DETAILS']
                except Exception as e:
                    write_log(e)
                    query = None
            conditions = f"and DE_No in({info_table['depot']}) and FA_CodeFamille='{data_row['CATEGORY']}'"
            begin = datetime.strptime(begin, "%d/%m/%Y").strftime("%Y-%m-%d")
            end = datetime.strptime(end, "%d/%m/%Y").strftime("%Y-%m-%d")
            if query is not None:
                lists = {
                    'STK_INTIALE': f"{query} DL_MvtStock IN (1,3) and DL_DateBL<='{begin}' {conditions}",
                    'EN_RETOUR': f"{query} do_domaine IN (0) and Dl_QTE < 0 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'EN_RECEP': f"{query} do_domaine IN (1) and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'EN_PROD': f"{query} do_type IN (40) and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'EN_ASSEMB': None,
                    'EN_TRANS': f"{query} do_type IN (23) and dl_mvtstock=1 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'EN_MVM': f"{query} do_type IN (20) and DO_PIECE not like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'EN_INV': f"{query} do_type IN (20) and DO_PIECE like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'TOTAL_EN': None,
                    'SO_VENTE': f"{query} do_domaine IN (0) and Dl_QTE > 0 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'SO_CONSO': f"{query} do_type IN (41) and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'SO_DESAS': None,
                    'SO_TRANS': f"{query} do_type IN (23) and dl_mvtstock=3 and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'SO_MVM': f"{query} do_type IN (21) and DO_PIECE not like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'SO_INV': f"{query} do_type IN (21) and DO_PIECE like'i00%' and DL_DateBL between '{begin}' and '{end}' {conditions}",
                    'TOTAL_SO': None,
                    'STK_FINAL_CAL': None,
                    'STK_FINAL_SYS': f"{query} DL_MvtStock IN (1,3) and DL_DateBL<='{end}' {conditions}"
                }
                count = 1

                for key, value in lists.items():
                    if count == int(colonneCheck['col']) - 2:
                        details = get_data(
                            sql=value,
                            columns=["PIECE", "DATE", "REF", "DESIGNATION", "QTE", "CMUP", "TOTAL"],
                            conn=check
                        )
                        if details is not None:
                            datas = details.to_dict(orient="records")
                        break
                    count += 1  # Incrémenter le compteur à chaque itération

            check.close()


    except Exception as e:
        write_log(f"Erreur de {str(e)}")
    response_data = {
        'data': datas,
    }
    return JsonResponse(response_data, safe=False)

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


