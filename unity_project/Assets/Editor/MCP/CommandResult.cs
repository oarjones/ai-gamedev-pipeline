[System.Serializable]
public class CommandResult
{
    public bool Success;
    public string ReturnValue; // Serializamos todo a string para simplicidad
    public string ConsoleOutput;
    public string ErrorMessage;
}