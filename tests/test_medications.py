def test_medication_crud_lifecycle(client):
    # 1. Create User
    u_res = client.post("/users", json={"name": "George Brown", "age": 82})
    assert u_res.status_code == 201
    user_id = u_res.json()["id"]

    # 2. Add Medication with multiple timings
    med_res = client.post("/medications", json={
        "user_id": user_id,
        "name": "Metformin",
        "dosage": "500mg",
        "instructions": "Take with breakfast and dinner",
        "times": ["08:00", "19:00"]
    })
    assert med_res.status_code == 201
    med_data = med_res.json()
    med_id = med_data["id"]
    assert med_data["name"] == "Metformin"
    assert len(med_data["schedules"]) == 2

    # 3. Retrieve user medications
    get_res = client.get(f"/medications/{user_id}")
    assert get_res.status_code == 200
    meds_list = get_res.json()
    assert len(meds_list) == 1
    assert meds_list[0]["id"] == med_id

    # 4. Update Medication (new times and dosage)
    put_res = client.put(f"/medications/{med_id}", json={
        "dosage": "1000mg",
        "times": ["08:00", "13:00", "20:00"]
    })
    assert put_res.status_code == 200
    updated_med = put_res.json()
    assert updated_med["dosage"] == "1000mg"
    assert len(updated_med["schedules"]) == 3

    # 5. Delete Medication
    del_res = client.delete(f"/medications/{med_id}")
    assert del_res.status_code == 204

    # Verify deleted
    get_after = client.get(f"/medications/{user_id}")
    assert get_after.status_code == 200
    assert len(get_after.json()) == 0


def test_create_medication_nonexistent_user(client):
    res = client.post("/medications", json={
        "user_id": 9999,
        "name": "Aspirin",
        "dosage": "100mg",
        "times": ["09:00"]
    })
    assert res.status_code == 404
    assert res.json()["detail"] == "User not found"
