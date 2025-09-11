using UnityEngine;

public class PlayerController : MonoBehaviour {
    public float moveSpeed = {{player_speed}}f;
    public float jumpHeight = {{jump_height}}f;
    private Rigidbody2D rb;

    void Awake() { rb = GetComponent<Rigidbody2D>(); }
    void Update() {
        float h = Input.GetAxis("Horizontal");
        rb.velocity = new Vector2(h * moveSpeed, rb.velocity.y);
        if (Input.GetButtonDown("Jump")) { rb.velocity = new Vector2(rb.velocity.x, jumpHeight); }
    }
}

