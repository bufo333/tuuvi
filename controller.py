from flask import Flask, render_template, request, g, session, flash, \
     redirect, url_for, abort
from flask_openid import OpenID

from sqlalchemy import create_engine, Table, Column, Integer, String, ForeignKey, Boolean
from sqlalchemy.orm import scoped_session, sessionmaker, relationship, backref
from sqlalchemy.ext.declarative import declarative_base

# setup flask
app = Flask(__name__)
app.config.update(
    DATABASE_URI = 'sqlite:///some.db',
    SECRET_KEY = 'development key',
    DEBUG = True
)

# setup flask-openid
oid = OpenID(app)



# setup sqlalchemy
engine = create_engine(app.config['DATABASE_URI'])
db_session = scoped_session(sessionmaker(autocommit=False,
                                         autoflush=False,
                                         bind=engine))
Base = declarative_base()
Base.query = db_session.query_property()

def init_db():
    Base.metadata.create_all(bind=engine)
    print "creating db"

membership_table = Table('membership_table', Base.metadata,
                         Column('UserID', Integer, ForeignKey('users.id')),
                         Column('GroupID', Integer, ForeignKey('groups.id')),
                         Column('approved', Boolean)
)

class Breakloop(Exception): pass

class User(Base):
    __tablename__ = 'users'
    id = Column(Integer, primary_key=True)
    name = Column(String(60))
    email = Column(String(200))
    openid = Column(String(200))
    founded = relationship('Group', backref='founder')
    groups = relationship('Group',secondary=membership_table)

    def __init__(self, name, email, openid,):
        self.name = name
        self.email = email
        self.openid = openid



class Group(Base):
    __tablename__ = 'groups'
    id = Column(Integer, primary_key=True)
    name = Column(String(60))
    description = Column(String(140))
    catagory = Column(String(50))
    user_id = Column(Integer, ForeignKey('users.id'))
    members = relationship('User',secondary=membership_table)

    def __init__(self, name, description, user_id, members):
        self.name = name
        self.description = description
        self.user_id = user_id
        self.members = members

    def __get_members(self):
        return [member.name for member in self.members]

    def __add_member(self,value):

        try:
            for member in self.members:
                if member.id == value.id:
                    self.members.remove(value)
                    raise Breakloop
            self.members.append(value)
        except Breakloop:
            pass
    str_members = property(__get_members,__add_member)

@app.before_request
def before_request():
    g.user = None
    if 'openid' in session:
        g.user = User.query.filter_by(openid=session['openid']).first()


@app.after_request
def after_request(response):
    db_session.remove()
    return response


@app.route('/')
def index():
    print next.__str__
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
@oid.loginhandler
def login():
    """Does the login via OpenID. Has to call into `oid.try_login`
to start the OpenID machinery.
"""
    # if we are already logged in, go back to were we came from
    if g.user is not None:
        return redirect(oid.get_next_url())

    if request.method == 'POST':
        openid = request.form.get('openid_identifier')
        if openid:
            return oid.try_login(openid, ask_for=['email', 'fullname',
                                                  'nickname',])

    return render_template('login.html', next=oid.get_next_url(),
                           error=oid.fetch_error())


@oid.after_login
def create_or_login(resp):
    """This is called when login with OpenID succeeded and it's not
necessary to figure out if this is the users's first login or not.
This function has to redirect otherwise the user will be presented
with a terrible URL which we certainly don't want.
"""
    session['openid'] = resp.identity_url
    user = User.query.filter_by(openid=resp.identity_url).first()

    if user is not None:
        flash(u'Successfully signed in')
        g.user = user
        return redirect(oid.get_next_url())

    return redirect(url_for('create_profile', next=oid.get_next_url(),
                            name=resp.fullname or resp.nickname,
                            email=resp.email, image=resp.image,))


@app.route('/create-profile', methods=['GET', 'POST'])
def create_profile():
    """If this is the user's first login, the create_or_login function
will redirect here so that the user can set up his profile.
"""
    if g.user is not None or 'openid' not in session:
        return redirect(url_for('index'))

    if request.method == 'POST':
        name = request.form['name']
        email = request.form['email']

        if not name:
            flash(u'Error: you have to provide a name')

        elif '@' not in email:
            flash(u'Error: you have to enter a valid email address')

        else:
            flash(u'Profile successfully created')
            db_session.add(User(name, email, session['openid']))
            db_session.commit()
            return redirect(oid.get_next_url())

    return render_template('create_profile.html', next_url=oid.get_next_url())


@app.route('/profile', methods=['GET', 'POST'])
def edit_profile():
    """Updates a profile"""

    if g.user is None:
        return redirect(url_for('index'))

    form = dict(name=g.user.name, email=g.user.email)

    if request.method == 'POST':

        if 'delete' in request.form:
            db_session.delete(g.user)
            db_session.commit()
            session['openid'] = None
            flash(u'Profile deleted')
            return redirect(url_for('index'))

        if 'update' in request.form:
            g.user.name = request.form['name']
            g.user.email = request.form['email']
            db_session.commit()
            flash(u'Profile Updated')
            return redirect(url_for('edit_profile'))

        if not form['name']:
            flash(u'Error: you have to provide a name')
        elif '@' not in form['email']:
            flash(u'Error: you have to enter a valid email address')

    return render_template('edit_profile.html', form=form)


@app.route('/logout')
def logout():
    session.pop('openid', None)
    flash(u'You have been signed out')
    return redirect(oid.get_next_url())

def determin_groups(offset,page=1):
    page = page
    limit = 10
    groups =[]
    groupsraw = None
    print "before ", len(groups), page, offset
    offset= int(offset)
    print offset
    groupsraw = Group.query.offset(offset).limit(11)
    for result in groupsraw:
        memberof = False
        founderof = False

        for member in result.members:
            if g.user != None:
                if member.id == g.user.id:
                    memberof = True
        if g.user != None:
            if result.user_id == g.user.id:
                founderof = True
        groups.append([result,memberof,founderof])
    print "len of groups ", len(groups)

    return(groups,limit)

2
@app.route('/groups/', methods=['GET'])
@app.route('/groups/<int:page>', methods=['GET'])
def groups_view(page=1,offset=0):
    page=page


    menu=False
    if page == 1:
        nextp = page
        prevp = page
        (groups,limit) = determin_groups(0,page)
        if (len(groups)) == 0:
            session['offset'] = 0
            print " equal to 0"
        if (len(groups)) > limit:
            print " not zero", len(groups)
            nextp = page + 1
            session['offset'] = (len(groups)-1)
            print "group list   ", len(groups)
            print "page ", page
            groups = groups[:10]



    else:

        prevp = page -1
        (groups,limit) = determin_groups(session['offset'],page)
        if (len(groups)) > limit:
            nextp = page + 1
            session['offset'] = (len(groups)-1)
        if (len(groups))<= limit and len(groups) > 0:
            nextp = page
            session['offset'] = (len(groups)-1)
            prevp = page - 1
            print "groups < limit ",(len(groups)-1)


    if g.user:
        for group in groups:
            if group[0].user_id == g.user.id:
                menu = True

    return render_template('groups.html', groups=groups, form=dict(name='',desc=''), page=page, nextp=nextp, prevp=prevp, menu=menu, offset=session['offset'])




@app.route('/groups/', methods=['POST'])
@app.route('/groups/<int:page>', methods=['POST'])

def groups_post(page=1):
    """Lets a user search for and join groups"""
    menu = False

    if 'leave' in request.form:
        print request.form['group_to_leave']
        group = Group.query.filter_by(id=int(request.form['group_to_leave'])).first()
        print group.name
        print group.str_members
        group.str_members = g.user
        db_session.commit()
        return redirect(url_for('groups_view', page=page))

    if 'add' in request.form:
        name = request.form['name']
        description = request.form['desc']
        user_id = g.user.id

        if not name:
            flash(u'Error: you have to provide a name!')
            return redirect(url_for('groups_view', form=dict(name=name,desc=description)))
        elif not description:
            flash(u'Error: you have to enter a valid description!')
            return redirect(url_for('groups_view', form=dict(name=name,desc=description)))

        db_session.add(Group(name,description,user_id,[g.user]))
        db_session.commit()
        flash(u'You have sucessfully added a group')
        return redirect(url_for('groups_view'))

    if 'delete' in request.form:
        group = request.form.getlist('do_delete')
        for group in group:
            group=Group.query.filter_by(id=group).first()
            db_session.delete(group)
            db_session.commit()
        flash(u'You have removed a group')
        return redirect(url_for('groups_view',page=page))


@app.route('/group/home/')
@app.route('/group/home/<name>')
def group_detail_view(name=None):
    name = name
    group = Group.query.filter_by(name=name).first()
    if name == None:
        return redirect(url_for('groups_view'))
    print name
    return render_template('group.html',group=group)






if __name__ == '__main__':
    init_db()
    app.run()
