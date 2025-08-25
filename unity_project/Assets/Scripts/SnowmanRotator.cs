using UnityEngine;

public class SnowmanRotator : MonoBehaviour
{
    public float rotationSpeed = 30f; // Degrees per second

    void Update()
    {
        transform.Rotate(0, rotationSpeed * Time.deltaTime, 0);
    }
}
