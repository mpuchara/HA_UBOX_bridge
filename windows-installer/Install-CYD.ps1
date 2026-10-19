# Serves local ESP Web Tools content on 127.0.0.1 without Python/PlatformIO.
$ErrorActionPreference='Stop'
$root=Split-Path -Parent $MyInvocation.MyCommand.Path
$files=@{
  '/'='index.html'
  '/index.html'='index.html'
  '/manifest.json'='manifest.json'
  '/manifest-ili9341.json'='manifest-ili9341.json'
  '/firmware/ubox-cyd-ili9341.bin'='firmware/ubox-cyd-ili9341.bin'
  '/firmware/ubox-cyd-esp32.bin'='firmware/ubox-cyd-esp32.bin'
  '/firmware/SHA256SUMS.txt'='firmware/SHA256SUMS.txt'
}
$types=@{'.html'='text/html; charset=utf-8';'.json'='application/json; charset=utf-8';'.bin'='application/octet-stream';'.txt'='text/plain; charset=utf-8'}
$listener=$null
foreach($port in 8765..8770){
  try {
    $candidate=[System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback,[int]$port)
    $candidate.Start()
    $listener=$candidate
    break
  }catch{}
}
if($null -eq $listener){ Write-Host 'Porty 8765-8770 sa zajete.' -ForegroundColor Red;exit 1 }
$port=([System.Net.IPEndPoint]$listener.LocalEndpoint).Port
$url="http://127.0.0.1:$port/"
Write-Host "Instalator UBox CYD: $url" -ForegroundColor Green
Write-Host 'Podlacz CYD i wybierz COM4 w przegladarce Edge/Chrome.'
Write-Host 'Zamknij to okno dopiero po instalacji.'
try{
  try { Start-Process 'msedge.exe' -ArgumentList $url -ErrorAction Stop }
  catch { Start-Process $url }
  while($true){
    $client=$null
    try{
      $client=$listener.AcceptTcpClient()
      $client.ReceiveTimeout=8000
      $client.SendTimeout=30000
      $stream=$client.GetStream()
      $reader=[System.IO.StreamReader]::new($stream,[System.Text.Encoding]::ASCII,$false,1024,$true)
      $request=$reader.ReadLine()
      if(-not $request){continue}
      for($n=0;$n -lt 64;$n++){
        $line=$reader.ReadLine()
        if($null -eq $line -or $line -eq ''){break}
      }
      $components=$request.Split(' ')
      $route=if($components.Length -gt 1){$components[1].Split('?')[0]}else{'/'}
      $status='200 OK'
      $body=[byte[]]@()
      $contentType='text/plain; charset=utf-8'
      if($components[0] -ne 'GET'){
        $status='405 Method Not Allowed'
        $body=[Text.Encoding]::UTF8.GetBytes('Only GET permitted')
      }elseif(-not $files.ContainsKey($route)){
        $status='404 Not Found'
        $body=[Text.Encoding]::UTF8.GetBytes('Not found')
      }else{
        $file=Join-Path $root $files[$route]
        if([IO.File]::Exists($file)){
          $body=[IO.File]::ReadAllBytes($file)
          $ext=[IO.Path]::GetExtension($file).ToLowerInvariant()
          if($types.ContainsKey($ext)){$contentType=$types[$ext]}
        }else{
          $status='404 Not Found'
          $body=[Text.Encoding]::UTF8.GetBytes('Missing file')
        }
      }
      $headers="HTTP/1.1 $status"+[char]13+[char]10+"Content-Type: $contentType"+[char]13+[char]10+"Content-Length: $($body.Length)"+[char]13+[char]10+"Cache-Control: no-store"+[char]13+[char]10+"Connection: close"+[char]13+[char]10+[char]13+[char]10
      $bytes=[Text.Encoding]::ASCII.GetBytes($headers)
      $stream.Write($bytes,0,$bytes.Length)
      if($body.Length -gt 0){$stream.Write($body,0,$body.Length)}
      $stream.Flush()
    }catch{
      Write-Host 'Przerwane zapytanie HTTP; instalator nadal dziala.'
    }finally{
      if($null -ne $client){$client.Close()}
    }
  }
}finally{
  if($null -ne $listener){$listener.Stop()}
}
