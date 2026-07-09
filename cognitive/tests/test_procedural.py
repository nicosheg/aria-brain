import sys
sys.path.insert(0, '.')
from cognitive.memory.procedural import ProceduralMemory

def test_procedural_add():
    mem = ProceduralMemory()
    proc = mem.add(
        name="Pitch ARIA to a clinic",
        description="Pitch AI automation to a dental clinic",
        steps=["Research clinic", "Generate audit", "Create proposal", "Follow up"],
        when_to_use="When a clinic expresses interest in automation",
        success_rate=0.6
    )
    assert proc.id is not None
    assert proc.name == "Pitch ARIA to a clinic"
    assert len(proc.steps) == 4
    assert mem.count() == 1
    print("✅ Procedural add: OK")

def test_procedural_search():
    mem = ProceduralMemory()
    mem.add("Pitch ARIA to a clinic", "Pitch AI automation", ["Step1"], "when clinic interested")
    mem.add("Onboard client", "Onboard new ARIA clients", ["StepA", "StepB"], "when client signs")
    
    results = mem.search("clinic")
    assert len(results) == 1
    # The keyword is in the name, not description
    assert "clinic" in results[0].name.lower()
    print("✅ Procedural search: OK")

def test_procedural_get_by_use_case():
    mem = ProceduralMemory()
    mem.add("Pitch ARIA", "Pitch automation", [], "When clinic shows interest")
    mem.add("Onboard client", "Onboard new clients", [], "When client signs contract")
    
    results = mem.get_by_use_case("interest")
    assert len(results) == 1
    assert "interest" in results[0].when_to_use.lower()
    print("✅ Procedural get_by_use_case: OK")

def test_procedural_record_use():
    mem = ProceduralMemory()
    proc = mem.add("Test procedure", "A test", ["Step"], "test", success_rate=0.5)
    
    mem.record_use(proc.id, success=True)
    mem.record_use(proc.id, success=True)
    mem.record_use(proc.id, success=False)
    
    assert proc.times_used == 3
    assert proc.times_succeeded == 2
    assert proc.success_rate == 2/3
    print("✅ Procedural record_use: OK")

if __name__ == "__main__":
    test_procedural_add()
    test_procedural_search()
    test_procedural_get_by_use_case()
    test_procedural_record_use()
    print("\n🎉 All Procedural Memory tests passed!")
