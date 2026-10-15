from aria_agent.intelligence import CognitiveCore
from aria_agent.runtime import AriaRuntime


def test_objective_fact_questions_route_to_source_backed_research():
    core = CognitiveCore()
    runtime = AriaRuntime.__new__(AriaRuntime)

    prompts = (
        "What is a derivative?",
        "What's a derivative?",
        "Who is Marie Curie?",
        "How does photosynthesis work?",
        "Is water H2O?",
        "When was Python first released?",
        "Define a derivative",
    )
    for prompt in prompts:
        frame = core.classify(prompt)
        assert frame.requires_web is True, prompt
        assert "research_operator" in frame.workers, (prompt, frame.workers)
        assert runtime._should_use_fast_lane(frame) is False, prompt


def test_memory_greetings_writing_and_ordinary_advice_do_not_auto_research():
    core = CognitiveCore()
    runtime = AriaRuntime.__new__(AriaRuntime)

    greeting = core.classify("Hello ARIA")
    assert greeting.intent == "greeting"
    assert greeting.requires_web is False
    assert runtime._should_use_fast_lane(greeting) is True

    memory = core.classify("What do you remember about me?")
    assert memory.intent == "memory"
    assert memory.requires_web is False
    assert runtime._should_use_fast_lane(memory) is True

    advice = core.classify("What should I focus on next?")
    assert advice.requires_web is False
    assert "research_operator" not in advice.workers
    assert runtime._should_use_fast_lane(advice) is True

    personalized_recommendation = core.classify(
        "Based on what you know about me, what is the one thing I should focus on for the future?"
    )
    assert personalized_recommendation.requires_web is False
    assert "research_operator" not in personalized_recommendation.workers
    assert runtime._should_use_fast_lane(personalized_recommendation) is True

    business_advice = core.classify(
        "If I wanted to start a business now what are your top 3 best advice for me"
    )
    assert business_advice.requires_web is False
    assert "research_operator" not in business_advice.workers
    assert runtime._should_use_fast_lane(business_advice) is True

    writing = core.classify(
        "Write a cover letter for this role while mentioning what a derivative is"
    )
    assert writing.requires_web is False
    assert "application_builder" in writing.workers
    assert "research_operator" not in writing.workers
    assert runtime._should_use_fast_lane(writing) is False
