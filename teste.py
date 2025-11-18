import subprocess
import random
import time
import sys
from multiprocessing import Pool, cpu_count, Manager
import os
import copy
import json
from datetime import datetime


# =============================================================================
# ### CONFIGURAÇÃO PRINCIPAL (HARD-CODED) ###
# =============================================================================
# Edite o caminho do executável aqui
EXECUTABLE_PATH = "./modelo10.exe"

# Tempo limite total em minutos
TIME_LIMIT_MINUTES = 50

REPORT_PATH = "resultado_pattern_search.json"


# Número de processos paralelos (Multi-Start)
WORKER_COUNT = 8

# =============================================================================
# ### FUNÇÃO 1: SETUP INTERATIVO ###
# =============================================================================
def get_user_input(prompt, type_caster, validation=None):
    """Função auxiliar para obter e validar input do usuário."""
    while True:
        try:
            value = type_caster(input(prompt))
            if validation is None or validation(value):
                return value
            else:
                print(f"Erro: Entrada inválida. Tente novamente.")
        except ValueError:
            print(f"Erro: Formato inválido. Tente novamente.")

def setup_parameters():
    """Faz todas as perguntas ao usuário para configurar a otimização."""
    print("="*60)
    print("Configuração da Otimização - Pattern Search Dinâmico")
    print("="*60)
    
    # 1. Objetivo
    obj_prompt = "Qual o objetivo? (max / min): "
    obj_str = get_user_input(obj_prompt, str, lambda v: v.lower() in ['max', 'min'])
    objective_multiplier = 1.0 if obj_str.lower() == 'max' else -1.0
    
    # 2. Número de Parâmetros
    num_params = get_user_input("Quantos parâmetros o executável recebe? ", int, lambda v: v > 0)
    
    param_definitions = []
    
    print("\n--- Configuração de Cada Parâmetro ---")
    
    # 3. Loop por cada parâmetro
    for i in range(num_params):
        print(f"\n--- Parâmetro {i+1} de {num_params} ---")
        
        # 3a. Tipo
        p_type_prompt = f"Qual o tipo do parâmetro {i+1}? (cat / int): "
        p_type = get_user_input(p_type_prompt, str, lambda v: v.lower() in ['cat', 'int'])
        
        if p_type.lower() == 'cat':
            # 3b. Categórico
            options_prompt = "Digite as opções separadas por vírgula (ex: baixo,medio,alto): "
            options_str = get_user_input(options_prompt, str, lambda v: len(v) > 0)
            options_list = [opt.strip() for opt in options_str.split(',')]
            
            param_definitions.append({
                'type': 'cat',
                'options': options_list
            })
            
        elif p_type.lower() == 'int':
            # 3c. Inteiro
            p_min = get_user_input(f"Valor MÍNIMO para o parâmetro {i+1}: ", int)
            p_max = get_user_input(f"Valor MÁXIMO para o parâmetro {i+1}: ", int, lambda v: v >= p_min)
            
            param_definitions.append({
                'type': 'int',
                'min': p_min,
                'max': p_max
            })

    print("\n" + "="*60)
    print("Configuração Concluída!")
    print("="*60 + "\n")
    
    return objective_multiplier, param_definitions

# =============================================================================
# ### FUNÇÃO 2: AVALIAÇÃO (BLACK-BOX) ###
# =============================================================================
# (Definida no topo para que os workers do pool possam acessá-la)
def evaluate(params, objective_multiplier):
    """
    Executa o modelo externo e retorna seu valor de saída,
    já multiplicado pelo objetivo (para sempre maximizar).
    """
    str_params = [str(p) for p in params]
    command = [EXECUTABLE_PATH] + str_params
    
    try:
        result = subprocess.run(
            command,
            capture_output=True,
            text=True,
            check=True,
            timeout=30
        )
        
        output_str = result.stdout.strip()
        
        if ':' in output_str:
            value_part = output_str.split(':')[-1]
            output_value = float(value_part.strip())
        else:
            output_value = float(output_str) 
            
        return output_value * objective_multiplier
    
    except Exception as e:
        # Silencia a maioria dos erros para não poluir o console,
        # mas você pode descomentar a linha abaixo se precisar debugar.
        # print(f"AVISO: Falha ao avaliar {params}. Erro: {e}", file=sys.stderr)
        return -float('inf')

# =============================================================================
# ### FUNÇÃO 3: GERADOR ALEATÓRIO ###
# =============================================================================
def generate_random_individual(param_definitions):
    """Cria um ponto de partida aleatório com base nas definições."""
    individual = []
    for p_def in param_definitions:
        if p_def['type'] == 'cat':
            individual.append(random.choice(p_def['options']))
        elif p_def['type'] == 'int':
            individual.append(random.randint(p_def['min'], p_def['max']))
    return individual

# =============================================================================
# ### FUNÇÃO 4: O ALGORITMO (PATTERN SEARCH) - ATUALIZADO ###
# =============================================================================
def run_pattern_search(start_individual, param_definitions, end_time, objective_multiplier, results_queue):
    """
    Executa um Pattern Search local e reporta melhorias para a 'results_queue'.
    """
    
    current_best_individual = copy.deepcopy(start_individual)
    # Avalia o ponto inicial
    current_best_fitness = evaluate(current_best_individual, objective_multiplier)
    
    # Reporta o ponto inicial para o monitor
    if current_best_fitness > -float('inf'):
        results_queue.put((current_best_fitness, current_best_individual))
    
    int_ranges = [p['max'] - p['min'] for p in param_definitions if p['type'] == 'int']
    step_size = max(1, int(max(int_ranges) * 0.2) if int_ranges else 20)
    
    while step_size >= 1 and time.time() < end_time:
        improved_in_this_step = True
        
        while improved_in_this_step and time.time() < end_time:
            improved_in_this_step = False
            
            for i in range(len(param_definitions)):
                if time.time() > end_time: break
                
                p_def = param_definitions[i]
                best_neighbor_in_axis = current_best_individual
                best_fitness_in_axis = current_best_fitness
                
                if p_def['type'] == 'cat':
                    for new_option in p_def['options']:
                        if new_option == current_best_individual[i]: continue
                        
                        neighbor = copy.deepcopy(current_best_individual)
                        neighbor[i] = new_option
                        neighbor_fitness = evaluate(neighbor, objective_multiplier)
                        
                        if neighbor_fitness > best_fitness_in_axis:
                            best_fitness_in_axis = neighbor_fitness
                            best_neighbor_in_axis = neighbor
                        
                        if time.time() > end_time: break
                
                elif p_def['type'] == 'int':
                    for direction in [1, -1]:
                        neighbor = copy.deepcopy(current_best_individual)
                        new_val = neighbor[i] + (direction * step_size)
                        new_val = max(p_def['min'], min(p_def['max'], int(new_val)))
                        
                        if new_val == neighbor[i]: continue
                            
                        neighbor[i] = new_val
                        neighbor_fitness = evaluate(neighbor, objective_multiplier)
                        
                        if neighbor_fitness > best_fitness_in_axis:
                            best_fitness_in_axis = neighbor_fitness
                            best_neighbor_in_axis = neighbor
                        
                        if time.time() > end_time: break
                
                # ### ALTERAÇÃO AQUI ###
                # Se encontrou uma melhora neste eixo, reporta para a fila
                if best_fitness_in_axis > current_best_fitness:
                    current_best_fitness = best_fitness_in_axis
                    current_best_individual = best_neighbor_in_axis
                    
                    # Coloca o novo melhor na fila para o processo principal ver
                    results_queue.put((current_best_fitness, current_best_individual))
                    
                    improved_in_this_step = True
            
        step_size //= 2 

    # Sinaliza o fim (opcional, mas bom)
    return (current_best_fitness, current_best_individual)


# =============================================================================
# ### FUNÇÃO PRINCIPAL (ORQUESTRADOR) - ATUALIZADA ###
# =============================================================================

def save_report(
    start_time,
    end_time,
    objective_multiplier,
    best_value,
    best_individual,
    algorithm_name="Multi-Start Pattern Search"
):
    """Salva um relatório JSON com os principais resultados da execução."""
    report = {
        "inicio": datetime.fromtimestamp(start_time).strftime("%Y-%m-%d %H:%M:%S"),
        "fim": datetime.fromtimestamp(end_time).strftime("%Y-%m-%d %H:%M:%S"),
        "duracao_segundos": end_time - start_time,
        "objetivo": "max" if objective_multiplier == 1.0 else "min",
        "algoritmo": algorithm_name,
        "melhor_valor": best_value,
        "melhores_parametros": best_individual,
    }

    try:
        with open(REPORT_PATH, "w", encoding="utf-8") as f:
            json.dump(report, f, ensure_ascii=False, indent=4)
        print(f"\nRelatório salvo em: {REPORT_PATH}")
    except Exception as e:
        print(f"\n[AVISO] Não foi possível salvar o relatório em JSON: {e}")


def main():
    try:
        objective_multiplier, param_definitions = setup_parameters()
    except KeyboardInterrupt:
        print("\nConfiguração cancelada. Saindo.")
        return

    if not os.path.exists(EXECUTABLE_PATH):
        print(f"ERRO: Executável não encontrado em '{EXECUTABLE_PATH}'")
        return

    start_time = time.time()
    end_time = start_time + TIME_LIMIT_MINUTES * 60
    
    print(f"Iniciando Otimização - Multi-Start Pattern Search")
    print(f"Estratégia: {WORKER_COUNT} buscas locais paralelas")
    print(f"Início: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    print(f"Término previsto: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
    print("="*60)
    
    # Criar pontos de partida
    starting_points = []
    for _ in range(WORKER_COUNT):
        starting_points.append(generate_random_individual(param_definitions))
        
    print(f"Iniciando {WORKER_COUNT} buscas paralelas com os seguintes pontos aleatórios:")
    for i, point in enumerate(starting_points):
        print(f"  Worker {i+1}: {point}")
    
    manager = Manager()
    results_queue = manager.Queue()
    
    # Variáveis para acompanhar o melhor global
    global_best_fitness = -float('inf')
    global_best_individual = starting_points[0]
    
    print("\nOtimizando... (Monitorando resultados em tempo real)")

    try:
        with Pool(processes=WORKER_COUNT) as pool:
            
            async_results = []
            for point in starting_points:
                res = pool.apply_async(
                    run_pattern_search, 
                    args=(point, 
                          param_definitions, 
                          end_time, 
                          objective_multiplier, 
                          results_queue)
                )
                async_results.append(res)

            # Loop de monitoramento
            while time.time() < end_time:
                while not results_queue.empty():
                    try:
                        worker_fitness, worker_individual = results_queue.get_nowait()
                        
                        if worker_fitness > global_best_fitness:
                            global_best_fitness = worker_fitness
                            global_best_individual = worker_individual
                            
                            real_value = global_best_fitness * objective_multiplier
                            
                            print("\n*** NOVO MELHOR ENCONTRADO ***")
                            print(f"    -> Valor: {real_value:.4f}")
                            print(f"    -> Input: {global_best_individual}\n")
                            
                    except Exception:
                        pass
                
                time.sleep(0.2)

            print("Tempo esgotado. Encerrando workers...")
            pool.terminate()
            pool.join()

    except KeyboardInterrupt:
        # Se o usuário apertar CTRL+C no meio da otimização
        print("\nExecução interrompida pelo usuário. Encerrando workers...")
        try:
            pool.terminate()
            pool.join()
        except:
            pass

    # Momento real do fim (pode ser por tempo ou CTRL+C)
    real_end_time = time.time()
    run_duration = real_end_time - start_time
    
    best_overall_fitness = global_best_fitness * objective_multiplier
    best_overall_individual = global_best_individual
    
    print("\n" + "="*60)
    print("OTIMIZAÇÃO CONCLUÍDA")
    print("="*60)
    
    print("\n" + "="*60)
    print("RELATÓRIO FINAL DA ESTRATÉGIA")
    print("="*60)
    print(f"Estratégia Utilizada: Multi-Start Pattern Search ({WORKER_COUNT} execuções paralelas)")
    print(f"Tempo Total de Execução: {run_duration / 60:.2f} minutos")
    print("\n--- MELHOR RESULTADO ENCONTRADO ---")
    print(f"Melhor Valor Alcançado: {best_overall_fitness:.4f}")
    print(f"Sequência do Resultado: {best_overall_individual}")
    print("="*60)

    # >>> AQUI GERAMOS O ARQUIVO JSON <<<
    save_report(
        start_time=start_time,
        end_time=real_end_time,
        objective_multiplier=objective_multiplier,
        best_value=best_overall_fitness,
        best_individual=best_overall_individual,
        algorithm_name="Multi-Start Pattern Search"
    )

