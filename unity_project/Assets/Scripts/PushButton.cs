using UnityEngine;

public class PushButton : MonoBehaviour
{
    public Rigidbody targetRigidbody;
    public float pushForce = 100f;

    void OnMouseDown()
    {
        if (targetRigidbody != null)
        {
            // Apply force in the forward direction of the button
            targetRigidbody.AddForce(transform.forward * pushForce, ForceMode.Impulse);
            Debug.Log("Button pushed! Force applied to " + targetRigidbody.name);
        }
        else
        {
            Debug.LogWarning("Target Rigidbody not assigned to PushButton.");
        }
    }
}
