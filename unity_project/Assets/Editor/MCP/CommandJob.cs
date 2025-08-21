using System.Threading.Tasks;

public class CommandJob
{
    public string CommandToExecute { get; set; }
    public TaskCompletionSource<string> Tcs { get; set; }
}