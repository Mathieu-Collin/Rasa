#!/usr/bin/env python3
"""
Test du système de gestion d'erreurs et circuit breaker
Validation robuste pour le LLM Intent Router
"""

import sys
import time

# Ajouter les chemins
sys.path.insert(0, "/workspace")


def test_error_handling_system():
    """Test complet du système de gestion d'erreurs"""

    print("🛡️  Test du système de gestion d'erreurs LLM Intent Router")
    print("=========================================================")

    # Import des modules d'exceptions
    from src.exceptions.ollama_exceptions import (
        CircuitBreaker,
        CircuitBreakerState,
        OllamaAPIError,
        OllamaConnectionError,
        OllamaErrorType,
        OllamaParsingError,
        OllamaTimeoutError,
        RetryPolicy,
    )

    # 1. Test des exceptions spécialisées
    print("\n1️⃣ Test des exceptions spécialisées...")

    exception_tests = [
        {
            "name": "OllamaConnectionError",
            "exception_class": OllamaConnectionError,
            "args": ["Connexion échouée", "http://172.22.0.2:11434"],
            "expected_type": OllamaErrorType.CONNECTION_ERROR,
        },
        {
            "name": "OllamaTimeoutError",
            "exception_class": OllamaTimeoutError,
            "args": ["Timeout dépassé", 30.0],
            "expected_type": OllamaErrorType.TIMEOUT_ERROR,
        },
        {
            "name": "OllamaAPIError",
            "exception_class": OllamaAPIError,
            "args": ["Erreur API", 500, "Internal Server Error"],
            "expected_type": OllamaErrorType.API_ERROR,
        },
        {
            "name": "OllamaParsingError",
            "exception_class": OllamaParsingError,
            "args": ["Parsing échoué", "response malformée"],
            "expected_type": OllamaErrorType.PARSING_ERROR,
        },
    ]

    exception_success = 0
    for test in exception_tests:
        try:
            exc = test["exception_class"](*test["args"])

            # Vérifications
            if exc.error_type == test["expected_type"]:
                print(f"   ✅ {test['name']}: Type d'erreur correct")
                exception_success += 1
            else:
                print(f"   ❌ {test['name']}: Type incorrect")

            # Vérifier que l'exception a un timestamp
            if hasattr(exc, "timestamp") and exc.timestamp > 0:
                print(f"   ✅ {test['name']}: Timestamp présent")
            else:
                print(f"   ❌ {test['name']}: Timestamp manquant")

        except Exception as e:
            print(f"   ❌ {test['name']}: Erreur création exception: {e}")

    print(f"   📊 Tests exceptions: {exception_success}/{len(exception_tests)} réussis")

    # 2. Test du Circuit Breaker
    print("\n2️⃣ Test du Circuit Breaker...")

    cb = CircuitBreaker(failure_threshold=3, recovery_timeout=2.0, success_threshold=2)

    # État initial
    assert cb.state == CircuitBreakerState.CLOSED, "État initial incorrect"
    assert cb.can_execute() == True, "Devrait pouvoir exécuter initialement"
    print("   ✅ État initial CLOSED correct")

    # Simulation d'échecs successifs
    print("   🔄 Simulation d'échecs successifs...")
    for i in range(3):
        cb.record_failure()
        print(
            f"      Échec {i + 1}: état={cb.state.value}, failures={cb.failure_count}"
        )

    # Vérifier transition vers OPEN
    assert cb.state == CircuitBreakerState.OPEN, "Devrait être OPEN après 3 échecs"
    assert cb.can_execute() == False, "Ne devrait pas pouvoir exécuter en état OPEN"
    print("   ✅ Transition vers OPEN après échecs")

    # Attendre le timeout de récupération
    print("   ⏳ Attente du timeout de récupération...")
    time.sleep(2.1)  # Un peu plus que recovery_timeout

    # Vérifier transition vers HALF_OPEN
    can_exec = cb.can_execute()
    assert cb.state == CircuitBreakerState.HALF_OPEN, (
        "Devrait être HALF_OPEN après timeout"
    )
    assert can_exec == True, "Devrait pouvoir exécuter en HALF_OPEN"
    print("   ✅ Transition vers HALF_OPEN après timeout")

    # Simulation de succès pour fermer le circuit
    print("   🔄 Simulation de succès pour fermeture...")
    for i in range(2):
        cb.record_success()
        print(f"      Succès {i + 1}: état={cb.state.value}")

    # Vérifier transition vers CLOSED
    assert cb.state == CircuitBreakerState.CLOSED, "Devrait être CLOSED après succès"
    print("   ✅ Transition vers CLOSED après succès")

    # Test des statistiques
    stats = cb.get_stats()
    expected_stats = [
        "state",
        "failure_count",
        "total_calls",
        "failure_rate",
        "success_rate",
    ]
    stats_valid = all(key in stats for key in expected_stats)

    if stats_valid:
        print("   ✅ Statistiques du circuit breaker complètes")
        print(f"      Taux d'échec: {stats['failure_rate']:.2f}")
        print(f"      Taux de succès: {stats['success_rate']:.2f}")
        print(f"      Changements d'état: {stats['state_changes']}")
    else:
        print("   ❌ Statistiques incomplètes")

    # 3. Test de la politique de retry
    print("\n3️⃣ Test de la politique de retry...")

    retry_policy = RetryPolicy(max_retries=3, base_delay=1.0, backoff_factor=2.0)

    # Test des délais
    delays = [retry_policy.get_delay(i) for i in range(5)]
    expected_pattern = [0.0, 1.0, 2.0, 4.0, 8.0]  # 0, base, base*2, base*4, base*8

    delay_correct = True
    for i, (actual, expected) in enumerate(zip(delays, expected_pattern)):
        if abs(actual - expected) > 0.1:  # Tolérance
            print(f"   ❌ Délai incorrect pour tentative {i}: {actual} vs {expected}")
            delay_correct = False

    if delay_correct:
        print("   ✅ Progression des délais correcte")
        print(f"      Délais: {[f'{d:.1f}s' for d in delays]}")

    # Test des conditions de retry
    retry_tests = [
        {
            "attempt": 1,
            "exception": OllamaTimeoutError("Timeout", 30.0),
            "should_retry": True,
        },
        {
            "attempt": 3,  # max_retries
            "exception": OllamaTimeoutError("Timeout", 30.0),
            "should_retry": False,
        },
        {
            "attempt": 1,
            "exception": OllamaAPIError("Not found", 404, ""),
            "should_retry": False,  # Erreur 404 ne doit pas être retryée
        },
    ]

    retry_success = 0
    for test in retry_tests:
        should_retry = retry_policy.should_retry(test["attempt"], test["exception"])
        if should_retry == test["should_retry"]:
            print(
                f"   ✅ Retry test: tentative {test['attempt']}, {test['exception'].__class__.__name__}"
            )
            retry_success += 1
        else:
            print(
                f"   ❌ Retry test: attendu {test['should_retry']}, obtenu {should_retry}"
            )

    print(f"   📊 Tests retry: {retry_success}/{len(retry_tests)} réussis")

    # 4. Test d'intégration avec client Ollama mocké
    print("\n4️⃣ Test d'intégration avec gestion d'erreurs...")

    def simulate_ollama_call_with_errors(
        circuit_breaker, retry_policy, should_fail=False, error_type="timeout"
    ):
        """Simule un appel Ollama avec gestion d'erreurs"""

        if not circuit_breaker.can_execute():
            return None, "circuit_open"

        for attempt in range(1, retry_policy.max_retries + 1):
            try:
                if should_fail:
                    if error_type == "timeout":
                        raise OllamaTimeoutError("Simulated timeout", 30.0)
                    elif error_type == "connection":
                        raise OllamaConnectionError(
                            "Simulated connection error", "http://172.22.0.2:11434"
                        )
                    elif error_type == "api":
                        raise OllamaAPIError(
                            "Simulated API error", 500, "Internal error"
                        )
                else:
                    # Succès simulé
                    circuit_breaker.record_success()
                    return "greet", "success"

            except Exception as e:
                if retry_policy.should_retry(attempt, e):
                    delay = retry_policy.get_delay(attempt)
                    print(f"      Tentative {attempt} échouée, retry dans {delay}s")
                    if delay > 0:
                        time.sleep(min(delay, 0.1))  # Délai réduit pour les tests
                else:
                    circuit_breaker.record_failure(e)
                    return None, f"failed_after_{attempt}_attempts"

        circuit_breaker.record_failure()
        return None, "max_retries_exceeded"

    # Reset du circuit breaker pour les tests
    cb.reset()

    # Test avec succès
    result, status = simulate_ollama_call_with_errors(
        cb, retry_policy, should_fail=False
    )
    if result == "greet" and status == "success":
        print("   ✅ Appel réussi sans erreur")
    else:
        print(f"   ❌ Appel réussi incorrect: {result}, {status}")

    # Test avec échecs et retry
    result, status = simulate_ollama_call_with_errors(
        cb, retry_policy, should_fail=True, error_type="timeout"
    )
    if "failed" in status or "exceeded" in status:
        print("   ✅ Gestion d'échecs avec retry fonctionne")
    else:
        print(f"   ❌ Gestion d'échecs incorrecte: {status}")

    # 5. Calcul du score final
    print("\n5️⃣ Score final de validation...")

    components_tested = [
        exception_success == len(exception_tests),  # Exceptions
        cb.state == CircuitBreakerState.CLOSED,  # Circuit breaker
        delay_correct,  # Retry policy delays
        retry_success == len(retry_tests),  # Retry conditions
        stats_valid,  # Statistics
    ]

    total_score = sum(components_tested) / len(components_tested) * 100

    print(
        f"   📊 Composants validés: {sum(components_tested)}/{len(components_tested)}"
    )
    print(f"   🎯 Score final: {total_score:.1f}%")

    if total_score >= 80:
        print("\n🎉 SYSTÈME DE GESTION D'ERREURS VALIDÉ !")
        print("✅ Circuit breaker opérationnel")
        print("✅ Politique de retry configurée")
        print("✅ Exceptions spécialisées fonctionnelles")
        return True
    else:
        print("\n⚠️  Système partiellement validé - Améliorations requises")
        return False


if __name__ == "__main__":
    success = test_error_handling_system()
    exit(0 if success else 1)
