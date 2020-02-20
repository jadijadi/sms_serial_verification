function unfollow(username){
    var req = new XMLHttpRequest();
    req.open("POST", "unf", true);
    req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    req.send("unfollow=" + username);
    unfbtn = document.getElementById("butten-fol-" + username);
    unfbtn.innerHTML = "Follow";
    unfbtn.setAttribute("onclick", "follow('" + username + "')");
}
function follow(username){
    var req = new XMLHttpRequest();
    req.open("POST", "fol", true);
    req.setRequestHeader("Content-type", "application/x-www-form-urlencoded");
    req.send("follow=" + username);
    folbtn = document.getElementById("butten-fol-" + username);
    folbtn.innerHTML = "Unfollow";
    folbtn.setAttribute("onclick", "unfollow('" + username + "')");
}
