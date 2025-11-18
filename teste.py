import subprocess
import random
import time
import sys
from multiprocessing import Pool, cpu_count, Manager
import os
import copy

# =============================================================================
# ### CONFIGURAÇÃO PRINCIPAL (HARD-CODED) ###
# =============================================================================
# Edite o caminho do executável aqui
EXECUTABLE_PATH = "./modelo10.exe"

# Tempo limite total em minutos
TIME_LIMIT_MINUTES = 10

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
    print("Configuração da Otimização")
    print("="*60)

    # 1. Escolha do algoritmo
    print("\nAlgoritmos disponíveis:")
    print("  ps     - Pattern Search (busca local)")
    print("  ga     - Algoritmo Genético (busca global)")
    print("  hybrid - Híbrido (GA primeiro, depois PS para refinamento)")
    algo_prompt = "\nQual algoritmo deseja usar? (ps / ga / hybrid): "
    algorithm = get_user_input(algo_prompt, str, lambda v: v.lower() in ['ps', 'ga', 'hybrid'])
    algorithm = algorithm.lower()

    # 2. Objetivo
    obj_prompt = "Qual o objetivo? (max / min): "
    obj_str = get_user_input(obj_prompt, str, lambda v: v.lower() in ['max', 'min'])
    objective_multiplier = 1.0 if obj_str.lower() == 'max' else -1.0
    
    # 3. Número de Parâmetros
    num_params = get_user_input("Quantos parâmetros o executável recebe? ", int, lambda v: v > 0)
    
    param_definitions = []
    
    print("\n--- Configuração de Cada Parâmetro ---")

    # 4. Loop por cada parâmetro
    for i in range(num_params):
        print(f"\n--- Parâmetro {i+1} de {num_params} ---")

        # 4a. Tipo
        p_type_prompt = f"Qual o tipo do parâmetro {i+1}? (cat / int): "
        p_type = get_user_input(p_type_prompt, str, lambda v: v.lower() in ['cat', 'int'])

        if p_type.lower() == 'cat':
            # 4b. Categórico
            options_prompt = "Digite as opções separadas por vírgula (ex: baixo,medio,alto): "
            options_str = get_user_input(options_prompt, str, lambda v: len(v) > 0)
            options_list = [opt.strip() for opt in options_str.split(',')]

            param_definitions.append({
                'type': 'cat',
                'options': options_list
            })

        elif p_type.lower() == 'int':
            # 4c. Inteiro
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

    return algorithm, objective_multiplier, param_definitions

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
# ### FUNÇÕES DO ALGORITMO GENÉTICO ###
# =============================================================================
def tournament_selection(population, fitnesses, tournament_size=3):
    """Seleção por torneio - escolhe o melhor de um grupo aleatório."""
    tournament_indices = random.sample(range(len(population)), tournament_size)
    tournament_fitnesses = [fitnesses[i] for i in tournament_indices]
    winner_idx = tournament_indices[tournament_fitnesses.index(max(tournament_fitnesses))]
    return copy.deepcopy(population[winner_idx])

def crossover(parent1, parent2, param_definitions):
    """Crossover de um ponto - combina dois pais para criar um filho."""
    if len(parent1) <= 1:
        return copy.deepcopy(parent1)

    crossover_point = random.randint(1, len(parent1) - 1)
    child = parent1[:crossover_point] + parent2[crossover_point:]
    return child

def mutate(individual, param_definitions, mutation_rate=0.1):
    """Mutação - altera aleatoriamente genes do indivíduo."""
    mutated = copy.deepcopy(individual)

    for i in range(len(mutated)):
        if random.random() < mutation_rate:
            p_def = param_definitions[i]

            if p_def['type'] == 'cat':
                # Mutação categórica: escolhe outra opção aleatória
                mutated[i] = random.choice(p_def['options'])

            elif p_def['type'] == 'int':
                # Mutação inteira: adiciona valor aleatório dentro do range
                range_size = p_def['max'] - p_def['min']
                mutation_amount = random.randint(-range_size // 10, range_size // 10)
                mutated[i] = max(p_def['min'], min(p_def['max'], mutated[i] + mutation_amount))

    return mutated

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
# ### FUNÇÃO 5: ALGORITMO GENÉTICO ###
# =============================================================================
def run_genetic_algorithm(param_definitions, end_time, objective_multiplier, results_queue,
                          population_size=50, mutation_rate=0.1, elitism_count=2):
    """
    Executa um Algoritmo Genético e reporta melhorias para a 'results_queue'.

    Parâmetros:
    - population_size: Tamanho da população
    - mutation_rate: Taxa de mutação (0.0 a 1.0)
    - elitism_count: Número de melhores indivíduos preservados por geração
    """

    # Inicializa população aleatória
    population = [generate_random_individual(param_definitions) for _ in range(population_size)]

    # Avalia população inicial
    fitnesses = [evaluate(ind, objective_multiplier) for ind in population]

    # Encontra melhor da população inicial
    best_idx = fitnesses.index(max(fitnesses))
    best_fitness = fitnesses[best_idx]
    best_individual = copy.deepcopy(population[best_idx])

    # Reporta melhor inicial
    if best_fitness > -float('inf'):
        results_queue.put((best_fitness, best_individual))

    generation = 0

    # Loop evolutivo
    while time.time() < end_time:
        generation += 1

        # Ordena população por fitness (do melhor para o pior)
        sorted_indices = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)

        # Elitismo: preserva os melhores
        new_population = [copy.deepcopy(population[i]) for i in sorted_indices[:elitism_count]]

        # Gera novos indivíduos até completar a população
        while len(new_population) < population_size:
            if time.time() > end_time:
                break

            # Seleção de pais
            parent1 = tournament_selection(population, fitnesses)
            parent2 = tournament_selection(population, fitnesses)

            # Crossover
            child = crossover(parent1, parent2, param_definitions)

            # Mutação
            child = mutate(child, param_definitions, mutation_rate)

            new_population.append(child)

        # Substitui população
        population = new_population

        # Avalia nova população
        fitnesses = [evaluate(ind, objective_multiplier) for ind in population]

        # Verifica se encontrou novo melhor
        current_best_idx = fitnesses.index(max(fitnesses))
        current_best_fitness = fitnesses[current_best_idx]
        current_best_individual = population[current_best_idx]

        if current_best_fitness > best_fitness:
            best_fitness = current_best_fitness
            best_individual = copy.deepcopy(current_best_individual)

            # Reporta melhoria
            results_queue.put((best_fitness, best_individual))

    return (best_fitness, best_individual)

# =============================================================================
# ### FUNÇÃO 6: ESTRATÉGIA HÍBRIDA (GA + PS) ###
# =============================================================================
def run_hybrid_algorithm(param_definitions, end_time, objective_multiplier, results_queue,
                         ga_time_ratio=0.6, population_size=50, mutation_rate=0.1):
    """
    Executa uma estratégia híbrida: Algoritmo Genético seguido de Pattern Search.

    Fase 1 (GA): Explora o espaço de busca globalmente
    Fase 2 (PS): Refina localmente as melhores soluções encontradas

    Parâmetros:
    - ga_time_ratio: Porcentagem do tempo total dedicada ao GA (padrão: 60%)
    - population_size: Tamanho da população do GA
    - mutation_rate: Taxa de mutação do GA
    """

    start_time = time.time()
    total_time = end_time - start_time
    ga_end_time = start_time + (total_time * ga_time_ratio)

    # =============================================================================
    # FASE 1: ALGORITMO GENÉTICO (Exploração Global)
    # =============================================================================

    # Inicializa população aleatória
    population = [generate_random_individual(param_definitions) for _ in range(population_size)]
    fitnesses = [evaluate(ind, objective_multiplier) for ind in population]

    # Encontra melhor inicial
    best_idx = fitnesses.index(max(fitnesses))
    best_fitness = fitnesses[best_idx]
    best_individual = copy.deepcopy(population[best_idx])

    if best_fitness > -float('inf'):
        results_queue.put((best_fitness, best_individual))

    generation = 0

    # Loop evolutivo do GA
    while time.time() < ga_end_time:
        generation += 1

        sorted_indices = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)
        new_population = [copy.deepcopy(population[i]) for i in sorted_indices[:2]]  # Elitismo

        while len(new_population) < population_size:
            if time.time() > ga_end_time:
                break

            parent1 = tournament_selection(population, fitnesses)
            parent2 = tournament_selection(population, fitnesses)
            child = crossover(parent1, parent2, param_definitions)
            child = mutate(child, param_definitions, mutation_rate)
            new_population.append(child)

        population = new_population
        fitnesses = [evaluate(ind, objective_multiplier) for ind in population]

        current_best_idx = fitnesses.index(max(fitnesses))
        current_best_fitness = fitnesses[current_best_idx]
        current_best_individual = population[current_best_idx]

        if current_best_fitness > best_fitness:
            best_fitness = current_best_fitness
            best_individual = copy.deepcopy(current_best_individual)
            results_queue.put((best_fitness, best_individual))

    # =============================================================================
    # FASE 2: PATTERN SEARCH (Refinamento Local)
    # =============================================================================

    # Pega os top 3 melhores indivíduos do GA como pontos de partida para PS
    sorted_indices = sorted(range(len(fitnesses)), key=lambda i: fitnesses[i], reverse=True)
    top_individuals = [copy.deepcopy(population[i]) for i in sorted_indices[:3]]

    # Executa Pattern Search em cada um dos top indivíduos
    for start_individual in top_individuals:
        if time.time() >= end_time:
            break

        current_best_individual = copy.deepcopy(start_individual)
        current_best_fitness = evaluate(current_best_individual, objective_multiplier)

        int_ranges = [p['max'] - p['min'] for p in param_definitions if p['type'] == 'int']
        step_size = max(1, int(max(int_ranges) * 0.2) if int_ranges else 20)

        while step_size >= 1 and time.time() < end_time:
            improved_in_this_step = True

            while improved_in_this_step and time.time() < end_time:
                improved_in_this_step = False

                for i in range(len(param_definitions)):
                    if time.time() > end_time:
                        break

                    p_def = param_definitions[i]
                    best_neighbor_in_axis = current_best_individual
                    best_fitness_in_axis = current_best_fitness

                    if p_def['type'] == 'cat':
                        for new_option in p_def['options']:
                            if new_option == current_best_individual[i]:
                                continue

                            neighbor = copy.deepcopy(current_best_individual)
                            neighbor[i] = new_option
                            neighbor_fitness = evaluate(neighbor, objective_multiplier)

                            if neighbor_fitness > best_fitness_in_axis:
                                best_fitness_in_axis = neighbor_fitness
                                best_neighbor_in_axis = neighbor

                            if time.time() > end_time:
                                break

                    elif p_def['type'] == 'int':
                        for direction in [1, -1]:
                            neighbor = copy.deepcopy(current_best_individual)
                            new_val = neighbor[i] + (direction * step_size)
                            new_val = max(p_def['min'], min(p_def['max'], int(new_val)))

                            if new_val == neighbor[i]:
                                continue

                            neighbor[i] = new_val
                            neighbor_fitness = evaluate(neighbor, objective_multiplier)

                            if neighbor_fitness > best_fitness_in_axis:
                                best_fitness_in_axis = neighbor_fitness
                                best_neighbor_in_axis = neighbor

                            if time.time() > end_time:
                                break

                    if best_fitness_in_axis > current_best_fitness:
                        current_best_fitness = best_fitness_in_axis
                        current_best_individual = best_neighbor_in_axis
                        results_queue.put((current_best_fitness, current_best_individual))
                        improved_in_this_step = True

            step_size //= 2

        # Atualiza melhor global se encontrou algo melhor
        if current_best_fitness > best_fitness:
            best_fitness = current_best_fitness
            best_individual = copy.deepcopy(current_best_individual)

    return (best_fitness, best_individual)

# =============================================================================
# ### FUNÇÃO PRINCIPAL (ORQUESTRADOR) - ATUALIZADA ###
# =============================================================================
def main():
    try:
        algorithm, objective_multiplier, param_definitions = setup_parameters()
    except KeyboardInterrupt:
        print("\nConfiguração cancelada. Saindo.")
        return

    if not os.path.exists(EXECUTABLE_PATH):
        print(f"ERRO: Executável não encontrado em '{EXECUTABLE_PATH}'")
        return

    start_time = time.time()
    end_time = start_time + TIME_LIMIT_MINUTES * 60

    # Define nome do algoritmo para exibição
    if algorithm == 'ps':
        algorithm_name = "Multi-Start Pattern Search"
    elif algorithm == 'ga':
        algorithm_name = "Algoritmo Genético"
    else:  # hybrid
        algorithm_name = "Estratégia Híbrida (GA + PS)"

    print(f"Iniciando Otimização - {algorithm_name}")
    if algorithm == 'ps':
        print(f"Estratégia: {WORKER_COUNT} buscas locais paralelas")
    elif algorithm == 'ga':
        print(f"Estratégia: {WORKER_COUNT} populações evolutivas paralelas")
    else:  # hybrid
        print(f"Estratégia: {WORKER_COUNT} execuções híbridas paralelas")
        print(f"  Fase 1 (60% do tempo): Algoritmo Genético (exploração global)")
        print(f"  Fase 2 (40% do tempo): Pattern Search (refinamento local)")
    print(f"Início: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(start_time))}")
    print(f"Término: {time.strftime('%Y-%m-%d %H:%M:%S', time.localtime(end_time))}")
    print("="*60)
    
    # Configura o Manager e a Queue para comunicação
    manager = Manager()
    results_queue = manager.Queue()

    # Variáveis para acompanhar o melhor global
    global_best_fitness = -float('inf')
    global_best_individual = None

    print("\nOtimizando... (Monitorando resultados em tempo real)")

    # Inicia o Pool de Processos
    with Pool(processes=WORKER_COUNT) as pool:

        # Lança todos os workers de forma assíncrona
        async_results = []

        if algorithm == 'ps':
            # Pattern Search: cria pontos de partida aleatórios
            starting_points = []
            for _ in range(WORKER_COUNT):
                starting_points.append(generate_random_individual(param_definitions))

            print(f"Iniciando {WORKER_COUNT} buscas paralelas com os seguintes pontos aleatórios:")
            for i, point in enumerate(starting_points):
                print(f"  Worker {i+1}: {point}")

            global_best_individual = starting_points[0]

            for point in starting_points:
                res = pool.apply_async(run_pattern_search,
                                       args=(point,
                                             param_definitions,
                                             end_time,
                                             objective_multiplier,
                                             results_queue))
                async_results.append(res)

        elif algorithm == 'ga':
            # Algoritmo Genético: lança múltiplas populações
            print(f"Iniciando {WORKER_COUNT} populações evolutivas paralelas")
            print(f"  Tamanho da população: 50 indivíduos cada")
            print(f"  Taxa de mutação: 10%")
            print(f"  Elitismo: 2 melhores preservados por geração")

            global_best_individual = generate_random_individual(param_definitions)

            for _ in range(WORKER_COUNT):
                res = pool.apply_async(run_genetic_algorithm,
                                       args=(param_definitions,
                                             end_time,
                                             objective_multiplier,
                                             results_queue))
                async_results.append(res)

        else:  # algorithm == 'hybrid'
            # Estratégia Híbrida: GA seguido de PS
            print(f"Iniciando {WORKER_COUNT} execuções híbridas paralelas")
            print(f"  População GA: 50 indivíduos")
            print(f"  Mutação GA: 10%")
            print(f"  Top 3 melhores do GA serão refinados com PS")

            global_best_individual = generate_random_individual(param_definitions)

            for _ in range(WORKER_COUNT):
                res = pool.apply_async(run_hybrid_algorithm,
                                       args=(param_definitions,
                                             end_time,
                                             objective_multiplier,
                                             results_queue))
                async_results.append(res)

        # Loop de monitoramento (executa no processo principal)
        try:
            while time.time() < end_time:
                # Verifica se há novos resultados na fila
                while not results_queue.empty():
                    try:
                        worker_fitness, worker_individual = results_queue.get_nowait()

                        # Compara com o melhor global
                        if worker_fitness > global_best_fitness:
                            global_best_fitness = worker_fitness
                            global_best_individual = worker_individual

                            # Imprime o valor real (desfazendo o multiplicador)
                            real_value = global_best_fitness * objective_multiplier

                            print("\n*** NOVO MELHOR ENCONTRADO ***")
                            print(f"    -> Valor: {real_value:.4f}")
                            print(f"    -> Input: {global_best_individual}\n")

                    except Exception:
                        # Ignora se a fila estiver vazia (condição de corrida)
                        pass

                # Pausa para não consumir 100% da CPU do processo principal
                time.sleep(0.2)

            print("Tempo esgotado. Encerrando workers...")

        except KeyboardInterrupt:
            print("\n\n*** INTERROMPIDO PELO USUÁRIO (Ctrl+C) ***")
            print("Encerrando workers e gerando relatório final...")

        finally:
            pool.terminate() # Força o encerramento dos workers
            pool.join()
        
    # ### FIM DAS ALTERAÇÕES ###
        
    run_duration = time.time() - start_time
    
    # O valor final é o último melhor que o monitor encontrou
    best_overall_fitness = global_best_fitness * objective_multiplier
    best_overall_individual = global_best_individual
    
    print("\n" + "="*60)
    print("OTIMIZAÇÃO CONCLUÍDA")
    print("="*60)
    
    print("\n" + "="*60)
    print("RELATÓRIO FINAL DA ESTRATÉGIA")
    print("="*60)
    print(f"Estratégia Utilizada: {algorithm_name} ({WORKER_COUNT} execuções paralelas)")
    print(f"Tempo Total de Execução: {run_duration / 60:.2f} minutos")
    print("\n--- MELHOR RESULTADO ENCONTRADO ---")
    print(f"Melhor Valor Alcançado: {best_overall_fitness:.4f}")
    print(f"Sequência do Resultado: {best_overall_individual}")
    print("="*60)

if __name__ == "__main__":
    detected_cpus = cpu_count()
    print(f"(Detectado {detected_cpus} processadores lógicos. Usando {WORKER_COUNT}.)")
    if WORKER_COUNT > detected_cpus:
        print(f"AVISO: Você pediu {WORKER_COUNT} processos, mas só {detected_cpus} foram detectados.")
    
    main()
